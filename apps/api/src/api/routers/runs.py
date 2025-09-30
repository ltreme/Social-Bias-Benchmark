from __future__ import annotations

from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

from fastapi import APIRouter, Query

from ..utils import ensure_db
from shared.storage.models import (
    BenchmarkRun,
    BenchmarkResult,
    Model,
    Case,
)
from analysis.benchmarks import analytics as bench_ana
from analysis.benchmarks.analytics import BenchQuery, load_benchmark_dataframe
from functools import lru_cache
from benchmark.pipeline.benchmark import run_benchmark_pipeline
from benchmark.repository.case import CaseRepository
from benchmark.repository.persona_repository import FullPersonaRepositoryByDataset
from benchmark.pipeline.adapters.prompting import LikertPromptFactory
from benchmark.pipeline.adapters.postprocess.postprocessor_likert import LikertPostProcessor
from benchmark.pipeline.adapters.persister_bench_sqlite import BenchPersisterPeewee
from benchmark.pipeline.adapters.llm import LlmClientFakeBench, LlmClientHFBench, LlmClientVLLMBench
import threading, time, traceback
import peewee as pw


router = APIRouter(tags=["runs"])


@router.get("/runs")
def list_runs() -> List[Dict[str, Any]]:
    ensure_db()
    out: List[Dict[str, Any]] = []
    for r in BenchmarkRun.select().join(Model).order_by(BenchmarkRun.id.desc()):
        out.append(
            {
                "id": int(r.id),
                "model_name": str(r.model_id.name),
                "include_rationale": bool(r.include_rationale),
                "dataset_id": int(r.dataset_id.id) if r.dataset_id else None,
                "created_at": str(r.created_at),
                "n_results": BenchmarkResult.select().where(BenchmarkResult.benchmark_run_id == r.id).count(),
            }
        )
    return out

@router.get("/runs/{run_id}")
def get_run(run_id: int) -> Dict[str, Any]:
    ensure_db()
    r = BenchmarkRun.get_or_none(BenchmarkRun.id == run_id)
    if not r:
        return {"id": run_id, "model_name": "unknown", "include_rationale": False, "dataset": None, "created_at": None}
    return {
        "id": int(r.id),
        "model_name": str(r.model_id.name),
        "include_rationale": bool(r.include_rationale),
        "n_results": BenchmarkResult.select().where(BenchmarkResult.benchmark_run_id == r.id).count(),
        "dataset": {
            "id": int(r.dataset_id.id) if r.dataset_id else None,
            "name": str(r.dataset_id.name) if r.dataset_id else None,
            "kind": str(r.dataset_id.kind) if r.dataset_id else None,
        } if r.dataset_id else None,
        "created_at": str(r.created_at),
    }


@router.get("/models")
def list_models() -> List[str]:
    ensure_db()
    return [m.name for m in Model.select()]


def _load_run_df(run_id: int):
    cfg = BenchQuery(run_ids=(run_id,))
    df = load_benchmark_dataframe(cfg)
    return df


@lru_cache(maxsize=64)
def _load_run_df_cached(run_id: int):
    # Cache the joined dataframe for expensive endpoints
    return _load_run_df(run_id)

def _df_for_read(run_id: int):
    """Return cached DF for finished runs; live DF while running."""
    info = _BENCH_PROGRESS.get(run_id, {})
    if info.get('status') in {'running', 'queued'}:
        return _load_run_df(run_id)
    return _load_run_df_cached(run_id)


# ---------------- Benchmark job control ----------------
_BENCH_PROGRESS: dict[int, dict] = {}

def _bench_progress_poller(run_id: int, dataset_id: int) -> None:
    try:
        while _BENCH_PROGRESS.get(run_id, {}).get("status") in {"queued", "running"}:
            _bench_update_progress(run_id, dataset_id)
            time.sleep(2.0)
    except Exception:
        pass

def _bench_update_progress(run_id: int, dataset_id: int) -> None:
    from shared.storage.models import BenchmarkResult, DatasetPersona, BenchmarkRun
    # Count completed triples incl. order
    done = (BenchmarkResult
            .select(BenchmarkResult.persona_uuid_id, BenchmarkResult.case_id, BenchmarkResult.scale_order)
            .where(BenchmarkResult.benchmark_run_id == run_id)
            .distinct()
            .count())
    try:
        cases = CaseRepository().count()
    except Exception:
        cases = 0
    total_personas = DatasetPersona.select().where(DatasetPersona.dataset_id == dataset_id).count()
    base_total = total_personas * cases if cases and total_personas else 0
    # Estimate duplicates by dual_fraction
    try:
        br = BenchmarkRun.get_by_id(run_id)
        frac = float(getattr(br, 'dual_fraction', 0.0) or 0.0)
    except Exception:
        frac = float(_BENCH_PROGRESS.get(run_id, {}).get('dual_fraction') or 0.0)
    extra = int(round(base_total * frac)) if base_total and frac else 0
    total = base_total + extra
    if done > total:
        total = done
    pct = (100.0 * done / total) if total else 0.0
    _BENCH_PROGRESS.setdefault(run_id, {})
    _BENCH_PROGRESS[run_id].update({"done": done, "total": total, "pct": pct})


def _bench_run_background(run_id: int) -> None:
    ensure_db()
    rec = BenchmarkRun.get_by_id(run_id)
    ds_id = int(rec.dataset_id.id)
    model_name = str(rec.model_id.name)
    include_rationale = bool(rec.include_rationale)
    scale_mode = getattr(rec, 'scale_mode', None) or _BENCH_PROGRESS.get(run_id, {}).get('scale_mode')
    dual_fraction = getattr(rec, 'dual_fraction', None) or _BENCH_PROGRESS.get(run_id, {}).get('dual_fraction')

    persona_repo = FullPersonaRepositoryByDataset(dataset_id=ds_id, model_name=model_name)
    question_repo = CaseRepository()
    max_new_toks = int(_BENCH_PROGRESS.get(run_id, {}).get('max_new_tokens', 256))
    system_prompt = rec.system_prompt
    prompt_factory = LikertPromptFactory(include_rationale=include_rationale, max_new_tokens=max_new_toks, system_preamble=system_prompt)
    post = LikertPostProcessor()
    backend = _BENCH_PROGRESS.get(run_id, {}).get('llm') or 'vllm'
    batch_size = int(_BENCH_PROGRESS.get(run_id, {}).get('batch_size') or (rec.batch_size or 2))
    if backend == 'fake':
        llm = LlmClientFakeBench(batch_size=batch_size)
    elif backend == 'hf':
        # Requires a configured model, for now fallback to fake if unavailable
        llm = LlmClientHFBench(model_name_or_path=model_name, batch_size=batch_size)
    else:
        import os
        base = _BENCH_PROGRESS.get(run_id, {}).get('vllm_base_url') or os.getenv('VLLM_BASE_URL') or 'http://localhost:8000'
        api_key = _BENCH_PROGRESS.get(run_id, {}).get('vllm_api_key') or os.getenv('VLLM_API_KEY')
        llm = LlmClientVLLMBench(base_url=str(base), model=model_name, api_key=api_key, batch_size=batch_size, max_new_tokens_cap=max_new_toks)

    persist = BenchPersisterPeewee()
    _BENCH_PROGRESS[run_id] = {**_BENCH_PROGRESS.get(run_id, {}), 'status': 'running'}
    try:
        skip_completed = bool(_BENCH_PROGRESS.get(run_id, {}).get('skip_completed', False))
        run_benchmark_pipeline(
            dataset_id=ds_id,
            question_repo=question_repo,
            persona_repo=persona_repo,
            prompt_factory=prompt_factory,
            llm=llm,
            post=post,
            persist=persist,
            model_name=model_name,
            benchmark_run_id=run_id,
            max_attempts=3,
            skip_completed_run_id=run_id if skip_completed else None,
            scale_mode=scale_mode,
            dual_fraction=float(dual_fraction) if isinstance(dual_fraction, (int,float)) else None,
        )
        _bench_update_progress(run_id, ds_id)
        info = _BENCH_PROGRESS.get(run_id, {})
        try:
            done = int(info.get('done') or 0)
            total = int(info.get('total') or 0)
        except Exception:
            done = 0; total = 0
        _BENCH_PROGRESS[run_id]['status'] = 'done' if (total == 0 or done >= total) else 'partial'
    except Exception as e:
        _BENCH_PROGRESS[run_id]['status'] = 'failed'
        _BENCH_PROGRESS[run_id]['error'] = str(e)
        try:
            print(f"[bench_run_background] run_id={run_id} failed: {e}")
            traceback.print_exc()
        except Exception:
            pass


@router.post("/benchmarks/start")
def start_benchmark(body: dict) -> dict:
    """Start a benchmark run for a dataset with a given model.

    Body: { dataset_id:int, model_name:str, include_rationale?:bool, llm?:'vllm'|'hf'|'fake', batch_size?:int, vllm_base_url?:str }
    Requires that attr-gen with same model is complete (client-side should ensure).
    """
    ensure_db()
    ds_id = int(body['dataset_id'])
    resume_run_id = body.get('resume_run_id')
    include_rationale = bool(body.get('include_rationale', False))
    llm = body.get('llm', 'vllm')
    batch_size = int(body.get('batch_size', 2))
    vllm_base_url = body.get('vllm_base_url')

    max_new_tokens = int(body.get('max_new_tokens', 256))
    max_attempts = int(body.get('max_attempts', 3))
    system_prompt = body.get('system_prompt')
    vllm_api_key = body.get('vllm_api_key')
    scale_mode = body.get('scale_mode')  # 'in' | 'rev' | 'random50'
    dual_fraction = body.get('dual_fraction')

    if resume_run_id is not None:
        # Resume existing run: update params on the existing record
        rec = BenchmarkRun.get_by_id(int(resume_run_id))
        if int(rec.dataset_id.id) != ds_id:
            raise ValueError("resume_run_id gehört zu einem anderen Dataset")
        # Use existing model of the run
        rec.include_rationale = include_rationale if 'include_rationale' in body else rec.include_rationale
        rec.batch_size = batch_size or rec.batch_size
        rec.max_attempts = max_attempts or rec.max_attempts
        rec.system_prompt = system_prompt if system_prompt is not None else rec.system_prompt
        if scale_mode in ('in','rev','random50'):
            try:
                rec.scale_mode = scale_mode
            except Exception:
                pass
        if isinstance(dual_fraction, (int, float)):
            try:
                rec.dual_fraction = float(dual_fraction)
            except Exception:
                pass
        rec.save()
        run_id = int(rec.id)
        _BENCH_PROGRESS[run_id] = {
            **_BENCH_PROGRESS.get(run_id, {}),
            'status': 'queued',
            'llm': llm,
            'batch_size': batch_size,
            'vllm_base_url': vllm_base_url,
            'vllm_api_key': vllm_api_key,
            'max_new_tokens': max_new_tokens,
            'skip_completed': True,
            'scale_mode': scale_mode,
            'dual_fraction': float(dual_fraction) if isinstance(dual_fraction, (int,float)) else None,
        }
    else:
        model_name = str(body['model_name'])
        model_entry, _ = Model.get_or_create(name=model_name)
        rec = BenchmarkRun.create(dataset_id=ds_id, model_id=model_entry.id, include_rationale=include_rationale, batch_size=batch_size, max_attempts=max_attempts, system_prompt=system_prompt, scale_mode=scale_mode, dual_fraction=float(dual_fraction) if isinstance(dual_fraction, (int,float)) else None)
        run_id = int(rec.id)
        _BENCH_PROGRESS[run_id] = {'status': 'queued', 'llm': llm, 'batch_size': batch_size, 'vllm_base_url': vllm_base_url, 'vllm_api_key': vllm_api_key, 'max_new_tokens': max_new_tokens, 'scale_mode': scale_mode, 'dual_fraction': float(dual_fraction) if isinstance(dual_fraction, (int,float)) else None}

    t = threading.Thread(target=_bench_run_background, args=(run_id,), daemon=True)
    t.start()
    # Start a lightweight poller to keep progress fresh during the run
    try:
        ds_id_int = int(ds_id)
        t_poll = threading.Thread(target=_bench_progress_poller, args=(run_id, ds_id_int), daemon=True)
        t_poll.start()
    except Exception:
        pass
    return {'ok': True, 'run_id': run_id}


@router.get("/benchmarks/{run_id}/status")
def bench_status(run_id: int) -> dict:
    ensure_db()
    info = _BENCH_PROGRESS.get(run_id)
    if not info:
        try:
            rec = BenchmarkRun.get_by_id(run_id)
            ds_id = int(rec.dataset_id.id)
            _bench_update_progress(run_id, ds_id)
            info = _BENCH_PROGRESS.get(run_id)
            if 'status' not in info:
                info['status'] = 'unknown'
        except Exception:
            info = {'status': 'unknown'}
    # Normalize status if incomplete
    try:
        d = int((info or {}).get('done') or 0)
        t = int((info or {}).get('total') or 0)
        if (t > 0 and d < t) and (info or {}).get('status') == 'done':
            info['status'] = 'partial'
    except Exception:
        pass
    return {'ok': True, **(info or {})}


@router.get("/runs/{run_id}/metrics")
def run_metrics(run_id: int) -> Dict[str, Any]:
    ensure_db()
    df = _df_for_read(run_id)
    if df.empty:
        return {"ok": True, "n": 0, "hist": {"bins": [], "shares": []}, "attributes": {}}
    s = df["rating"].dropna().astype(int)
    cats = list(range(int(s.min()), int(s.max()) + 1))
    counts = s.value_counts().reindex(cats, fill_value=0).sort_index()
    shares = (counts / counts.sum()).tolist()

    def attr_meta(col: str) -> Dict[str, Any]:
        if col not in df.columns:
            return {"categories": [], "baseline": None}
        work = df.copy()
        work[col] = work[col].fillna("Unknown")
        tab = bench_ana.summarise_rating_by(work, col)[[col, "count", "mean"]]
        base = None
        if not tab.empty:
            base = str(tab.sort_values("count", ascending=False)[col].iloc[0])
        cats_meta = [
            {"category": str(r[col]), "count": int(r["count"]), "mean": float(r["mean"]) }
            for _, r in tab.iterrows()
        ]
        return {"categories": cats_meta, "baseline": base}

    attrs = {k: attr_meta(k) for k in ["gender","origin_region","religion","sexuality","marriage_status","education"]}
    return {"ok": True, "n": int(len(df)), "hist": {"bins": [str(c) for c in cats], "shares": shares, "counts": [int(x) for x in counts.tolist()]}, "attributes": attrs}


@router.get("/runs/{run_id}/order-metrics")
def run_order_metrics(run_id: int) -> Dict[str, Any]:
    """Metrics for pairs asked in both directions (in vs. rev).

    Returns aggregate and per-case metrics based on normalised ratings where
    reversed answers are mapped to the normal direction already.
    """
    ensure_db()
    df = _df_for_read(run_id)
    if df.empty:
        return {"ok": True, "n_pairs": 0, "rma": {}, "obe": {}, "usage": {}, "test_retest": {}, "correlation": {}, "by_case": []}
    # Keep only rows with explicit scale_order
    if "scale_order" not in df.columns:
        return {"ok": True, "n_pairs": 0, "rma": {}, "obe": {}, "usage": {}, "test_retest": {}, "correlation": {}, "by_case": []}

    work = df.copy()
    # Build pairs by (persona, case)
    sub = work.loc[work["scale_order"].isin(["in", "rev"]) & work["rating"].notna(), ["persona_uuid", "case_id", "rating", "scale_order"]]
    if sub.empty:
        return {"ok": True, "n_pairs": 0, "rma": {}, "obe": {}, "usage": {}, "test_retest": {}, "correlation": {}, "by_case": []}
    piv = sub.pivot_table(index=["persona_uuid", "case_id"], columns="scale_order", values="rating", aggfunc="first").reset_index()
    if not ("in" in piv.columns and "rev" in piv.columns):
        return {"ok": True, "n_pairs": 0, "rma": {}, "obe": {}, "usage": {}, "test_retest": {}, "correlation": {}, "by_case": []}
    pairs = piv.dropna(subset=["in", "rev"]).copy()
    if pairs.empty:
        return {"ok": True, "n_pairs": 0, "rma": {}, "obe": {}, "usage": {}, "test_retest": {}, "correlation": {}, "by_case": []}
    pairs["diff"] = pairs["in"].astype(float) - pairs["rev"].astype(float)
    pairs["abs_diff"] = pairs["diff"].abs()

    # RMA
    exact = float((pairs["abs_diff"] == 0).mean()) if len(pairs) else 0.0
    mae = float(pairs["abs_diff"].mean()) if len(pairs) else 0.0
    try:
        from analysis.benchmarks.analytics import mann_whitney_cliffs
        _, _, cliffs = mann_whitney_cliffs(pairs["in"], pairs["rev"])
        cliffs = float(cliffs) if np.isfinite(cliffs) else float("nan")
    except Exception:
        cliffs = float("nan")

    # OBE = mean difference with 95% CI
    d = pairs["diff"].to_numpy(dtype=float)
    n = d.size
    mu = float(d.mean()) if n else 0.0
    sd = float(d.std(ddof=1)) if n > 1 else 0.0
    se = sd / np.sqrt(n) if n > 1 else 0.0
    ci_low = mu - 1.96 * se
    ci_high = mu + 1.96 * se

    # Usage metrics on all normalised ratings (both directions)
    s = pd.to_numeric(sub["rating"], errors="coerce").dropna()
    eei = float(((s == 1) | (s == 5)).mean()) if not s.empty else 0.0
    mni = float((s == 3).mean()) if not s.empty else 0.0
    sv = float(s.std(ddof=1)) if s.size > 1 else 0.0

    # Test-retest like
    within1 = float((pairs["abs_diff"] <= 1).mean()) if len(pairs) else 0.0
    mean_abs = mae

    # Correlations
    pear = float(pairs["in"].corr(pairs["rev"], method="pearson")) if len(pairs) > 1 else float("nan")
    spear = float(pairs["in"].corr(pairs["rev"], method="spearman")) if len(pairs) > 1 else float("nan")
    try:
        import scipy.stats as ss  # type: ignore
        kend = float(ss.kendalltau(pairs["in"], pairs["rev"]).correlation)
    except Exception:
        kend = float("nan")

    # Per-case breakdown
    rows: List[Dict[str, Any]] = []
    try:
        case_map = {str(r.id): (r.adjective or str(r.id)) for r in Case.select()}
    except Exception:
        case_map = {}
    for k, g in pairs.groupby("case_id"):
        ad = float((g["abs_diff"] == 0).mean()) if len(g) else 0.0
        rows.append({
            "case_id": str(k),
            "adjective": case_map.get(str(k)),
            "n_pairs": int(len(g)),
            "exact_rate": ad,
            "mae": float(g["abs_diff"].mean()) if len(g) else 0.0,
        })

    return {
        "ok": True,
        "n_pairs": int(len(pairs)),
        "rma": {"exact_rate": exact, "mae": mae, "cliffs_delta": cliffs},
        "obe": {"mean_diff": mu, "ci_low": ci_low, "ci_high": ci_high, "sd": sd},
        "usage": {"eei": eei, "mni": mni, "sv": sv},
        "test_retest": {"within1_rate": within1, "mean_abs_diff": mean_abs},
        "correlation": {"pearson": pear, "spearman": spear, "kendall": kend},
        "by_case": rows,
    }


@router.get("/runs/{run_id}/missing")
def run_missing(run_id: int) -> Dict[str, Any]:
    """Return count of missing BenchmarkResult pairs and a small sample.

    Missing = all (persona in dataset) × (cases) that have no BenchmarkResult for this run.
    Uses a SQL anti-join for efficiency.
    """
    ensure_db()
    from shared.storage.db import get_db
    db = get_db()
    rec = BenchmarkRun.get_or_none(BenchmarkRun.id == run_id)
    if not rec:
        return {"ok": False, "error": "run_not_found"}
    dataset_id = int(rec.dataset_id.id)

    # Total expected pairs and done
    cases_n = CaseRepository().count()
    from shared.storage.models import DatasetPersona
    personas_n = DatasetPersona.select().where(DatasetPersona.dataset_id == dataset_id).count()
    total = personas_n * cases_n
    done = (BenchmarkResult
            .select(BenchmarkResult.persona_uuid_id, BenchmarkResult.case_id)
            .where(BenchmarkResult.benchmark_run_id == run_id)
            .distinct()
            .count())

    # Count missing via anti-join
    cnt_sql = (
        "SELECT COUNT(1) AS missing "
        "FROM datasetpersona dp "
        "JOIN \"case\" c ON 1=1 "
        "LEFT JOIN benchmarkresult br "
        "  ON br.benchmark_run_id = ? AND br.persona_uuid_id = dp.persona_id AND br.case_id = c.id "
        "WHERE dp.dataset_id = ? AND br.id IS NULL"
    )
    missing = 0
    try:
        cur = db.execute_sql(cnt_sql, (run_id, dataset_id))
        row = cur.fetchone()
        if row:
            missing = int(row[0] or 0)
    except Exception:
        # Fallback: derive from total-done
        missing = max(0, (total or 0) - (done or 0))

    # Sample a few missing pairs with labels
    sample_sql = (
        "SELECT dp.persona_id, c.id AS case_id, c.adjective "
        "FROM datasetpersona dp "
        "JOIN \"case\" c ON 1=1 "
        "LEFT JOIN benchmarkresult br "
        "  ON br.benchmark_run_id = ? AND br.persona_uuid_id = dp.persona_id AND br.case_id = c.id "
        "WHERE dp.dataset_id = ? AND br.id IS NULL "
        "LIMIT 20"
    )
    samples = []
    try:
        cur = db.execute_sql(sample_sql, (run_id, dataset_id))
        for pid, cid, adj in cur.fetchall():
            samples.append({"persona_uuid": str(pid), "case_id": str(cid), "adjective": str(adj) if adj is not None else None})
    except Exception:
        samples = []

    return {"ok": True, "dataset_id": dataset_id, "total": total, "done": done, "missing": missing, "samples": samples}


@router.delete("/runs/{run_id}")
def delete_run(run_id: int) -> Dict[str, Any]:
    """Delete a benchmark run and all associated results.

    Thanks to FK constraints with ON DELETE CASCADE on BenchmarkResult.benchmark_run_id,
    removing the BenchmarkRun row also removes its BenchmarkResult rows.
    """
    ensure_db()
    # Clear progress cache if present
    try:
        if run_id in _BENCH_PROGRESS:
            _BENCH_PROGRESS.pop(run_id, None)
    except Exception:
        pass
    # Perform delete (cascades to results)
    try:
        deleted = BenchmarkRun.delete().where(BenchmarkRun.id == run_id).execute()
        try:
            _load_run_df_cached.cache_clear()
        except Exception:
            pass
        return {"ok": True, "deleted": int(deleted)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/runs/{run_id}/deltas")
def run_deltas(
    run_id: int,
    attribute: str,
    baseline: Optional[str] = None,
    n_perm: int = 1000,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    ensure_db()
    df = _df_for_read(run_id)
    if df.empty or attribute not in df.columns:
        return {"ok": True, "n": 0, "rows": []}
    # Compute table via analytics helper
    table = bench_ana.deltas_with_significance(df, attribute, baseline=baseline, n_perm=n_perm, alpha=alpha)

    # Add BH q-values
    try:
        qvals = bench_ana.benjamini_hochberg(table["p_value"].tolist())
        table = table.assign(q_value=qvals)
    except Exception:
        table = table.assign(q_value=[float("nan")] * len(table))

    # Add Cliff's delta per category vs baseline
    try:
        import pandas as _pd
        from analysis.benchmarks.analytics import mann_whitney_cliffs as _mw
        work = df.copy()
        work[attribute] = work[attribute].fillna("Unknown").astype(str)
        base = str(table["baseline"].iloc[0]) if "baseline" in table.columns and not table.empty else None
        if base is not None:
            base_vals = _pd.to_numeric(work.loc[work[attribute] == base, "rating"], errors="coerce").dropna()
            cliffs = []
            for _, r in table.iterrows():
                cat = str(r[attribute])
                vals = _pd.to_numeric(work.loc[work[attribute] == cat, "rating"], errors="coerce").dropna()
                _, _, cd = _mw(base_vals, vals)
                cliffs.append(float(cd))
            table = table.assign(cliffs_delta=cliffs)
    except Exception:
        table = table.assign(cliffs_delta=[float("nan")] * len(table))

    # Enrich with spread/CI based on SDs of baseline and category
    import pandas as _pd
    work = df.copy()
    work[attribute] = work[attribute].fillna("Unknown").astype(str)
    base = str(table["baseline"].iloc[0]) if "baseline" in table.columns and not table.empty else None
    base_vals = _pd.to_numeric(work.loc[work[attribute] == base, "rating"], errors="coerce").dropna() if base is not None else _pd.Series([], dtype=float)
    n_base = int(base_vals.shape[0]) if base is not None else 0
    mean_base = float(base_vals.mean()) if n_base > 0 else float('nan')
    sd_base = float(base_vals.std(ddof=1)) if n_base > 1 else float('nan')

    rows = []
    for _, r in table.iterrows():
        cat = str(r[attribute])
        vals = _pd.to_numeric(work.loc[work[attribute] == cat, "rating"], errors="coerce").dropna()
        n_cat = int(vals.shape[0])
        sd_cat = float(vals.std(ddof=1)) if n_cat > 1 else float('nan')
        delta = float(r["delta"]) if r["delta"] == r["delta"] else float('nan')
        # Standard error and CI of difference of means
        import math as _math
        if n_base > 1 and n_cat > 1 and _math.isfinite(sd_base) and _math.isfinite(sd_cat):
            se = float(_math.sqrt((sd_base ** 2) / n_base + (sd_cat ** 2) / n_cat))
            ci_low = float(delta - 1.96 * se) if _math.isfinite(delta) else None
            ci_high = float(delta + 1.96 * se) if _math.isfinite(delta) else None
        else:
            se = float('nan')
            ci_low = None
            ci_high = None
        rows.append({
            "category": cat,
            "count": int(round(r["count"])) ,
            "mean": float(r["mean"]),
            "delta": delta if delta == delta else None,
            "p_value": float(r["p_value"]) if r["p_value"] == r["p_value"] else None,
            "q_value": float(r.get("q_value", float("nan"))) if r.get("q_value", float("nan")) == r.get("q_value", float("nan")) else None,
            "cliffs_delta": float(r.get("cliffs_delta", float("nan"))) if r.get("cliffs_delta", float("nan")) == r.get("cliffs_delta", float("nan")) else None,
            "significant": bool(r.get("significant", False)),
            "baseline": base,
            "n_base": n_base,
            "sd_base": sd_base if sd_base == sd_base else None,
            "mean_base": mean_base if mean_base == mean_base else None,
            "n_cat": n_cat,
            "sd_cat": sd_cat if sd_cat == sd_cat else None,
            "mean_cat": float(vals.mean()) if n_cat > 0 else None,
            "se_delta": se if se == se else None,
            "ci_low": ci_low,
            "ci_high": ci_high,
        })
    return {"ok": True, "n": int(len(df)), "rows": rows, "baseline": base}


@router.get("/runs/{run_id}/means")
def run_means(run_id: int, attribute: str, top_n: Optional[int] = None) -> Dict[str, Any]:
    """Mean rating and counts per category for a given attribute."""
    ensure_db()
    import pandas as pd
    df = _df_for_read(run_id)
    if df.empty or attribute not in df.columns:
        return {"ok": True, "rows": []}
    work = df.copy()
    work[attribute] = work[attribute].fillna("Unknown").astype(str)
    s = pd.to_numeric(work["rating"], errors="coerce")
    g = work.assign(r=s).groupby(attribute)["r"].agg(["count","mean"]).reset_index()
    g = g.sort_values("count", ascending=False)
    if top_n and top_n > 0:
        g = g.head(int(top_n))
    rows = [{"category": str(r[attribute]), "count": int(r["count"]), "mean": float(r["mean"])} for _, r in g.iterrows()]
    return {"ok": True, "rows": rows}


@router.get("/runs/{run_id}/forest")
def run_forest(
    run_id: int,
    attribute: str,
    baseline: Optional[str] = None,
    target: Optional[str] = None,
    min_n: int = 1,
) -> Dict[str, Any]:
    ensure_db()
    df = _df_for_read(run_id)
    if df.empty or attribute not in df.columns:
        return {"ok": True, "n": 0, "rows": []}

    import pandas as pd
    import numpy as np

    work = df.copy()
    work[attribute] = work[attribute].fillna("Unknown").astype(str)
    if baseline is None:
        s = work.groupby(attribute)["rating"].size().sort_values(ascending=False)
        baseline = str(s.index[0]) if not s.empty else "Unknown"
    if target is None:
        s2 = work.loc[work[attribute] != baseline].groupby(attribute)["rating"].size().sort_values(ascending=False)
        target = str(s2.index[0]) if not s2.empty else None

    rows_list: List[Dict[str, Any]] = []
    for q, sub in work.groupby("case_id"):
        if not str(q).startswith("g"):
            continue
        base_vals = pd.to_numeric(sub.loc[sub[attribute] == baseline, "rating"], errors="coerce").dropna()
        cats = [target] if target is not None else [c for c in sub[attribute].unique().tolist() if str(c) != str(baseline)]
        for cat in cats:
            cat_vals = pd.to_numeric(sub.loc[sub[attribute] == cat, "rating"], errors="coerce").dropna()
            n_b = int(base_vals.shape[0])
            n_c = int(cat_vals.shape[0])
            if n_b < min_n or n_c < min_n:
                continue
            mean_b = float(base_vals.mean()) if n_b > 0 else float("nan")
            mean_c = float(cat_vals.mean()) if n_c > 0 else float("nan")
            delta = float(mean_c - mean_b) if np.isfinite(mean_b) and np.isfinite(mean_c) else float("nan")
            std_b = float(base_vals.std(ddof=1)) if n_b > 1 else float("nan")
            std_c = float(cat_vals.std(ddof=1)) if n_c > 1 else float("nan")
            se = float(np.sqrt((std_b ** 2) / n_b + (std_c ** 2) / n_c)) if (n_b > 1 and n_c > 1) else float("nan")
            ci_low = float(delta - 1.96 * se) if np.isfinite(se) else None
            ci_high = float(delta + 1.96 * se) if np.isfinite(se) else None
            rows_list.append({
                "case_id": str(q),
                "category": str(cat),
                "baseline": str(baseline),
                "n_base": n_b,
                "n_cat": n_c,
                "delta": delta,
                "se": se if np.isfinite(se) else None,
                "ci_low": ci_low,
                "ci_high": ci_high,
            })

    labels_map: Dict[str, str] = {str(c.id): str(c.adjective) for c in Case.select()}
    for r in rows_list:
        r["label"] = labels_map.get(r["case_id"], r["case_id"])  

    if rows_list:
        arr = pd.DataFrame(rows_list)
        if arr["se"].notna().any():
            sub = arr.loc[arr["se"].notna()].copy()
            w = 1.0 / (sub["se"] ** 2)
            w = w.replace([np.inf, -np.inf], np.nan).fillna(0.0)
            mu = float(np.nansum(w * sub["delta"]) / np.nansum(w)) if np.nansum(w) > 0 else float("nan")
            se_mu = float(np.sqrt(1.0 / np.nansum(w))) if np.nansum(w) > 0 else float("nan")
            overall = {"mean": mu if np.isfinite(mu) else None, "ci_low": mu - 1.96 * se_mu if np.isfinite(se_mu) else None, "ci_high": mu + 1.96 * se_mu if np.isfinite(se_mu) else None}
        else:
            overall = {"mean": None, "ci_low": None, "ci_high": None}
    else:
        overall = {"mean": None, "ci_low": None, "ci_high": None}

    rows_list.sort(key=lambda r: (r["delta"] if (r["delta"] == r["delta"]) else float('inf'), (r.get("label") or r["case_id"])) )
    return {"ok": True, "n": len(rows_list), "rows": rows_list, "overall": overall}
