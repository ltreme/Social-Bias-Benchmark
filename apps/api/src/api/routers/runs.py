from __future__ import annotations

from typing import Any, Dict, List, Optional

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
from benchmark.pipeline.benchmark import run_benchmark_pipeline
from benchmark.repository.case import CaseRepository
from benchmark.repository.persona_repository import FullPersonaRepositoryByDataset
from benchmark.pipeline.adapters.prompting import LikertPromptFactory
from benchmark.pipeline.adapters.postprocess.postprocessor_likert import LikertPostProcessor
from benchmark.pipeline.adapters.persister_bench_sqlite import BenchPersisterPeewee
from benchmark.pipeline.adapters.llm import LlmClientFakeBench, LlmClientHFBench, LlmClientVLLMBench
import threading, time, traceback


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
    from shared.storage.models import BenchmarkResult, DatasetPersona
    done = (BenchmarkResult
            .select(BenchmarkResult.persona_uuid_id, BenchmarkResult.case_id)
            .where(BenchmarkResult.benchmark_run_id == run_id)
            .distinct()
            .count())
    try:
        cases = CaseRepository().count()
    except Exception:
        cases = 0
    total_personas = DatasetPersona.select().where(DatasetPersona.dataset_id == dataset_id).count()
    total = total_personas * cases if cases and total_personas else 0
    pct = (100.0 * done / total) if total else 0.0
    _BENCH_PROGRESS.setdefault(run_id, {})
    _BENCH_PROGRESS[run_id].update({"done": done, "total": total, "pct": pct})


def _bench_run_background(run_id: int) -> None:
    ensure_db()
    rec = BenchmarkRun.get_by_id(run_id)
    ds_id = int(rec.dataset_id.id)
    model_name = str(rec.model_id.name)
    include_rationale = bool(rec.include_rationale)

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
        )
        _bench_update_progress(run_id, ds_id)
        _BENCH_PROGRESS[run_id]['status'] = 'done'
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
    model_name = str(body['model_name'])
    include_rationale = bool(body.get('include_rationale', False))
    llm = body.get('llm', 'vllm')
    batch_size = int(body.get('batch_size', 2))
    vllm_base_url = body.get('vllm_base_url')

    model_entry, _ = Model.get_or_create(name=model_name)
    max_new_tokens = int(body.get('max_new_tokens', 256))
    max_attempts = int(body.get('max_attempts', 3))
    system_prompt = body.get('system_prompt')
    vllm_api_key = body.get('vllm_api_key')
    rec = BenchmarkRun.create(dataset_id=ds_id, model_id=model_entry.id, include_rationale=include_rationale, batch_size=batch_size, max_attempts=max_attempts, system_prompt=system_prompt)
    _BENCH_PROGRESS[int(rec.id)] = {'status': 'queued', 'llm': llm, 'batch_size': batch_size, 'vllm_base_url': vllm_base_url, 'vllm_api_key': vllm_api_key, 'max_new_tokens': max_new_tokens}

    t = threading.Thread(target=_bench_run_background, args=(int(rec.id),), daemon=True)
    t.start()
    # Start a lightweight poller to keep progress fresh during the run
    try:
        ds_id_int = int(ds_id)
        t_poll = threading.Thread(target=_bench_progress_poller, args=(int(rec.id), ds_id_int), daemon=True)
        t_poll.start()
    except Exception:
        pass
    return {'ok': True, 'run_id': int(rec.id)}


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
    return {'ok': True, **(info or {})}


@router.get("/runs/{run_id}/metrics")
def run_metrics(run_id: int) -> Dict[str, Any]:
    ensure_db()
    df = _load_run_df(run_id)
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
    return {"ok": True, "n": int(len(df)), "hist": {"bins": [str(c) for c in cats], "shares": shares}, "attributes": attrs}


@router.get("/runs/{run_id}/deltas")
def run_deltas(
    run_id: int,
    attribute: str,
    baseline: Optional[str] = None,
    n_perm: int = 1000,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    ensure_db()
    df = _load_run_df(run_id)
    if df.empty or attribute not in df.columns:
        return {"ok": True, "n": 0, "rows": []}
    table = bench_ana.deltas_with_significance(df, attribute, baseline=baseline, n_perm=n_perm, alpha=alpha)
    rows = [
        {
            "category": str(r[attribute]),
            "count": int(round(r["count"])),
            "mean": float(r["mean"]),
            "delta": float(r["delta"]),
            "p_value": float(r["p_value"]),
            "significant": bool(r["significant"]),
            "baseline": str(r["baseline"]),
        }
        for _, r in table.iterrows()
    ]
    return {"ok": True, "n": int(len(df)), "rows": rows, "baseline": rows[0]["baseline"] if rows else baseline}


@router.get("/runs/{run_id}/forest")
def run_forest(
    run_id: int,
    attribute: str,
    baseline: Optional[str] = None,
    target: Optional[str] = None,
    min_n: int = 1,
) -> Dict[str, Any]:
    ensure_db()
    df = _load_run_df(run_id)
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
