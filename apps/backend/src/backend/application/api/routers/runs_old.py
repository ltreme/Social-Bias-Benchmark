from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
import traceback
from contextlib import nullcontext
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

import numpy as np
import pandas as pd
import peewee as pw
import requests
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.domain.analytics.benchmarks import analytics as bench_ana
from backend.domain.analytics.benchmarks.analytics import (
    BenchQuery,
    load_benchmark_dataframe,
)
from backend.domain.benchmarking.adapters.postprocess.postprocessor_likert import (
    LikertPostProcessor,
)
from backend.domain.benchmarking.adapters.prompting import LikertPromptFactory
from backend.domain.benchmarking.benchmark import (
    BenchmarkCancelledError,
    run_benchmark_pipeline,
)
from backend.infrastructure.benchmark.persister_bench_sqlite import BenchPersisterPeewee
from backend.infrastructure.benchmark.repository.persona_repository import (
    FullPersonaRepositoryByDataset,
)
from backend.infrastructure.benchmark.repository.trait import TraitRepository
from backend.infrastructure.llm import LlmClientFakeBench, LlmClientVLLMBench
from backend.infrastructure.storage.db import get_db
from backend.infrastructure.storage.models import (
    BenchCache,
    BenchmarkResult,
    BenchmarkRun,
    DatasetPersona,
    Model,
    Trait,
    utcnow,
)

from ..deps import db_session
from ..utils import ensure_db

router = APIRouter(tags=["runs"], dependencies=[Depends(db_session)])

_DEFAULT_ANALYSIS_ATTRIBUTES: List[str] = [
    "gender",
    "origin_subregion",
    "religion",
    "migration_status",
    "sexuality",
    "marriage_status",
    "education",
]
UNKNOWN_TRAIT_CATEGORY = "Unbekannt"
METRICS_CACHE_VERSION = 2


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
                "n_results": BenchmarkResult.select()
                .where(BenchmarkResult.benchmark_run_id == r.id)
                .count(),
            }
        )
    return out


@router.get("/runs/{run_id}")
def get_run(run_id: int) -> Dict[str, Any]:
    ensure_db()
    r = BenchmarkRun.get_or_none(BenchmarkRun.id == run_id)
    if not r:
        return {
            "id": run_id,
            "model_name": "unknown",
            "include_rationale": False,
            "dataset": None,
            "created_at": None,
        }
    return {
        "id": int(r.id),
        "model_name": str(r.model_id.name),
        "include_rationale": bool(r.include_rationale),
        "n_results": BenchmarkResult.select()
        .where(BenchmarkResult.benchmark_run_id == r.id)
        .count(),
        "dataset": (
            {
                "id": int(r.dataset_id.id) if r.dataset_id else None,
                "name": str(r.dataset_id.name) if r.dataset_id else None,
                "kind": str(r.dataset_id.kind) if r.dataset_id else None,
            }
            if r.dataset_id
            else None
        ),
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
    if info.get("status") in {"running", "queued"}:
        return _load_run_df(run_id)
    return _load_run_df_cached(run_id)


def _progress_status(info: Dict[str, Any]) -> str:
    try:
        done = int(info.get("done") or 0)
        total = int(info.get("total") or 0)
    except Exception:
        done = 0
        total = 0
    if total and done >= total:
        return "done"
    if done > 0:
        return "partial"
    return info.get("status") or "queued"


def _filter_by_trait_category(
    df: pd.DataFrame, trait_category: Optional[str]
) -> pd.DataFrame:
    if not trait_category:
        return df
    work = df.copy()
    work["trait_category"] = (
        work.get("trait_category").fillna(UNKNOWN_TRAIT_CATEGORY).astype(str)
    )
    return work.loc[work["trait_category"] == trait_category]


# ---------------- Persistent cache helpers ----------------
def _result_row_count(run_id: int) -> int:
    try:
        return int(
            BenchmarkResult.select()
            .where(BenchmarkResult.benchmark_run_id == run_id)
            .count()
        )
    except Exception:
        return 0


def _cache_key(run_id: int, kind: str, params: Dict[str, Any]) -> str:
    key = {"r": _result_row_count(run_id), **params}
    try:
        return json.dumps(key, sort_keys=True, ensure_ascii=False)
    except Exception:
        return json.dumps(
            {"r": key.get("r"), "params": str(params)},
            sort_keys=True,
            ensure_ascii=False,
        )


def _cache_get(run_id: int, kind: str, key: str) -> Optional[Dict[str, Any]]:
    try:
        rec = (
            BenchCache.select(BenchCache.data)
            .where(
                (BenchCache.run_id == run_id)
                & (BenchCache.kind == kind)
                & (BenchCache.key == key)
            )
            .first()
        )
        if not rec:
            return None
        return json.loads(rec.data)
    except Exception:
        return None


def _cache_put(run_id: int, kind: str, key: str, payload: Dict[str, Any]) -> None:
    try:
        data = json.dumps(payload, ensure_ascii=False)
        existing = (
            BenchCache.select()
            .where(
                (BenchCache.run_id == run_id)
                & (BenchCache.kind == kind)
                & (BenchCache.key == key)
            )
            .first()
        )
        if existing:
            existing.data = data
            existing.updated_at = utcnow()
            existing.save()
        else:
            BenchCache.create(run_id=run_id, kind=kind, key=key, data=data)
    except Exception:
        # Never fail the request due to cache issues
        pass


# ---------------- Benchmark job control ----------------
_BENCH_PROGRESS: dict[int, dict] = {}
_WARM_CACHE_JOBS: Dict[int, Dict[str, Any]] = {}
_WARM_CACHE_LOCK = threading.Lock()
_LOG = logging.getLogger(__name__)


def _bench_progress_poller(run_id: int, dataset_id: int) -> None:
    try:
        while _BENCH_PROGRESS.get(run_id, {}).get("status") in {
            "queued",
            "running",
            "cancelling",
        }:
            if _BENCH_PROGRESS.get(run_id, {}).get("cancel_requested"):
                _BENCH_PROGRESS[run_id]["status"] = "cancelling"
            _bench_update_progress(run_id, dataset_id)
            time.sleep(2.0)
    except Exception:
        pass


def _bench_update_progress(run_id: int, dataset_id: int) -> None:
    from backend.infrastructure.storage.models import (
        BenchmarkResult,
        BenchmarkRun,
        DatasetPersona,
    )

    # Count completed triples incl. order
    done = (
        BenchmarkResult.select(
            BenchmarkResult.persona_uuid_id,
            BenchmarkResult.case_id,
            BenchmarkResult.scale_order,
        )
        .where(BenchmarkResult.benchmark_run_id == run_id)
        .distinct()
        .count()
    )
    try:
        traits = TraitRepository().count()
    except Exception:
        traits = 0
    total_personas = (
        DatasetPersona.select().where(DatasetPersona.dataset_id == dataset_id).count()
    )
    base_total = total_personas * traits if traits and total_personas else 0
    # Estimate duplicates by dual_fraction
    try:
        br = BenchmarkRun.get_by_id(run_id)
        frac = float(getattr(br, "dual_fraction", 0.0) or 0.0)
    except Exception:
        frac = float(_BENCH_PROGRESS.get(run_id, {}).get("dual_fraction") or 0.0)
    extra = int(round(base_total * frac)) if base_total and frac else 0
    total = base_total + extra
    if done > total:
        total = done
    pct = (100.0 * done / total) if total else 0.0
    _BENCH_PROGRESS.setdefault(run_id, {})
    entry = _BENCH_PROGRESS[run_id]
    entry.update({"done": done, "total": total, "pct": pct})
    if entry.get("status") in (None, "unknown"):
        entry["status"] = _progress_status(entry)


def _completed_keys_for_run(run_id: int) -> set[tuple[str, str, str]]:
    from backend.infrastructure.storage.models import BenchmarkResult

    keys: set[tuple[str, str, str]] = set()
    q = BenchmarkResult.select(
        BenchmarkResult.persona_uuid_id,
        BenchmarkResult.case_id,
        BenchmarkResult.scale_order,
    ).where(BenchmarkResult.benchmark_run_id == int(run_id))
    for row in q:
        keys.add(
            (
                str(row.persona_uuid_id),
                str(row.case_id),
                str(row.scale_order or "in"),
            )
        )
    return keys


def _bench_run_background(run_id: int) -> None:
    ensure_db()
    rec = BenchmarkRun.get_by_id(run_id)
    ds_id = int(rec.dataset_id.id)
    model_name = str(rec.model_id.name)
    include_rationale = bool(rec.include_rationale)
    if _BENCH_PROGRESS.get(run_id, {}).get("cancel_requested"):
        _BENCH_PROGRESS[run_id] = {
            **_BENCH_PROGRESS.get(run_id, {}),
            "status": "cancelled",
            "error": "Benchmark wurde abgebrochen",
        }
        return
    scale_mode = getattr(rec, "scale_mode", None) or _BENCH_PROGRESS.get(
        run_id, {}
    ).get("scale_mode")
    dual_fraction = getattr(rec, "dual_fraction", None) or _BENCH_PROGRESS.get(
        run_id, {}
    ).get("dual_fraction")

    attrgen_run_id = _BENCH_PROGRESS.get(run_id, {}).get("attrgen_run_id")
    persona_repo = FullPersonaRepositoryByDataset(
        dataset_id=ds_id, model_name=model_name, attr_generation_run_id=attrgen_run_id
    )
    trait_repo = TraitRepository()
    max_new_toks = int(_BENCH_PROGRESS.get(run_id, {}).get("max_new_tokens", 256))
    system_prompt = rec.system_prompt
    prompt_factory = LikertPromptFactory(
        include_rationale=include_rationale,
        max_new_tokens=max_new_toks,
        system_preamble=system_prompt,
    )
    post = LikertPostProcessor()
    backend = _BENCH_PROGRESS.get(run_id, {}).get("llm") or "vllm"
    batch_size = int(
        _BENCH_PROGRESS.get(run_id, {}).get("batch_size") or (rec.batch_size or 2)
    )
    if backend == "fake":
        llm = LlmClientFakeBench(batch_size=batch_size)
    else:

        def _probe_models(u: str) -> dict:
            r = requests.get(
                u.rstrip("/") + "/v1/models",
                timeout=2.5,
                headers={"accept": "application/json"},
            )
            r.raise_for_status()
            return r.json()

        base_pref = (
            _BENCH_PROGRESS.get(run_id, {}).get("vllm_base_url")
            or os.getenv("VLLM_BASE_URL")
            or "http://localhost:8000"
        )
        # Build candidates similar to attrgen
        cands = []

        def _norm(url: str) -> str:
            try:
                p = urlparse(url)
                host = (p.hostname or "").lower()
                if host in {"localhost", "127.0.0.1"}:
                    p = p._replace(netloc=f"host.docker.internal:{p.port or 80}")
                    return urlunparse(p)
            except Exception:
                pass
            return url

        if base_pref:
            cands += [base_pref, _norm(base_pref)]
        envb = os.getenv("VLLM_BASE_URL")
        if envb:
            cands += [envb, _norm(envb)]
        cands += ["http://host.docker.internal:8000", "http://localhost:8000"]
        tried = []
        base = None
        for u in [x for i, x in enumerate(cands) if x and x not in cands[:i]]:
            try:
                data = _probe_models(u)
                ids = [
                    str(m.get("id"))
                    for m in (data.get("data") or [])
                    if isinstance(m, dict)
                ]
                if not ids or model_name in ids:
                    base = u
                    break
                tried.append((u, f"Modell '{model_name}' nicht gelistet"))
            except Exception as e:
                tried.append((u, str(e)))
        if base is None:
            _BENCH_PROGRESS[run_id] = {
                **_BENCH_PROGRESS.get(run_id, {}),
                "status": "failed",
                "error": f"vLLM nicht erreichbar oder Modell fehlt – versucht: {'; '.join([f'{u}: {err}' for u,err in tried])}",
            }
            return
        api_key = _BENCH_PROGRESS.get(run_id, {}).get("vllm_api_key") or os.getenv(
            "VLLM_API_KEY"
        )
        llm = LlmClientVLLMBench(
            base_url=str(base),
            model=model_name,
            api_key=api_key,
            batch_size=batch_size,
            max_new_tokens_cap=max_new_toks,
        )

    persist = BenchPersisterPeewee()
    _BENCH_PROGRESS[run_id] = {
        **_BENCH_PROGRESS.get(run_id, {}),
        "status": "running",
        "cancel_requested": _BENCH_PROGRESS.get(run_id, {}).get(
            "cancel_requested", False
        ),
    }

    def _cancel_check() -> bool:
        return bool(_BENCH_PROGRESS.get(run_id, {}).get("cancel_requested"))

    try:
        skip_completed = bool(
            _BENCH_PROGRESS.get(run_id, {}).get("skip_completed", False)
        )
        completed_keys = _completed_keys_for_run(run_id) if skip_completed else None
        persona_count = persona_repo.count(ds_id)
        run_benchmark_pipeline(
            dataset_id=ds_id,
            trait_repo=trait_repo,
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
            dual_fraction=(
                float(dual_fraction)
                if isinstance(dual_fraction, (int, float))
                else None
            ),
            persona_count_override=persona_count,
            completed_keys=completed_keys,
            cancel_check=_cancel_check,
        )
        _bench_update_progress(run_id, ds_id)
        info = _BENCH_PROGRESS.get(run_id, {})
        try:
            done = int(info.get("done") or 0)
            total = int(info.get("total") or 0)
        except Exception:
            done = 0
            total = 0
        _BENCH_PROGRESS[run_id]["status"] = (
            "done" if (total == 0 or done >= total) else "partial"
        )
    except BenchmarkCancelledError:
        _BENCH_PROGRESS[run_id]["status"] = "cancelled"
        _BENCH_PROGRESS[run_id]["error"] = "Benchmark wurde abgebrochen"
    except Exception as e:
        _BENCH_PROGRESS[run_id]["status"] = "failed"
        _BENCH_PROGRESS[run_id]["error"] = str(e)
        try:
            print(f"[bench_run_background] run_id={run_id} failed: {e}")
            traceback.print_exc()
        except Exception:
            pass


@router.post("/benchmarks/start")
def start_benchmark(body: dict) -> dict:
    """Start a benchmark run for a dataset with a given model.

    Body: { dataset_id:int, model_name:str, include_rationale?:bool, llm?:'vllm'|'fake', batch_size?:int, vllm_base_url?:str, attrgen_run_id?:int }
    If attrgen_run_id is provided, personas are enriched using attributes from that run.
    """
    ensure_db()
    ds_id = int(body["dataset_id"])
    resume_run_id = body.get("resume_run_id")
    include_rationale = bool(body.get("include_rationale", False))
    llm = body.get("llm", "vllm")
    batch_size = int(body.get("batch_size", 2))
    vllm_base_url = body.get("vllm_base_url")
    attrgen_run_id = body.get("attrgen_run_id")

    max_new_tokens = int(body.get("max_new_tokens", 256))
    max_attempts = int(body.get("max_attempts", 3))
    system_prompt = body.get("system_prompt")
    vllm_api_key = body.get("vllm_api_key")
    scale_mode = body.get("scale_mode")  # 'in' | 'rev' | 'random50'
    dual_fraction = body.get("dual_fraction")

    if resume_run_id is not None:
        # Resume existing run: update params on the existing record
        rec = BenchmarkRun.get_by_id(int(resume_run_id))
        if int(rec.dataset_id.id) != ds_id:
            raise ValueError("resume_run_id gehört zu einem anderen Dataset")
        # Use existing model of the run
        rec.include_rationale = (
            include_rationale if "include_rationale" in body else rec.include_rationale
        )
        rec.batch_size = batch_size or rec.batch_size
        rec.max_attempts = max_attempts or rec.max_attempts
        rec.system_prompt = (
            system_prompt if system_prompt is not None else rec.system_prompt
        )
        if scale_mode in ("in", "rev", "random50"):
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
            "status": "queued",
            "dataset_id": ds_id,
            "llm": llm,
            "batch_size": batch_size,
            "vllm_base_url": vllm_base_url,
            "vllm_api_key": vllm_api_key,
            "max_new_tokens": max_new_tokens,
            "skip_completed": True,
            "scale_mode": scale_mode,
            "dual_fraction": (
                float(dual_fraction)
                if isinstance(dual_fraction, (int, float))
                else None
            ),
            "attrgen_run_id": (
                int(attrgen_run_id) if attrgen_run_id is not None else None
            ),
            "cancel_requested": False,
        }
    else:
        model_name = str(body["model_name"])
        model_entry, _ = Model.get_or_create(name=model_name)
        rec = BenchmarkRun.create(
            dataset_id=ds_id,
            model_id=model_entry.id,
            include_rationale=include_rationale,
            batch_size=batch_size,
            max_attempts=max_attempts,
            system_prompt=system_prompt,
            scale_mode=scale_mode,
            dual_fraction=(
                float(dual_fraction)
                if isinstance(dual_fraction, (int, float))
                else None
            ),
        )
        run_id = int(rec.id)
        # Validate attrgen_run_id belongs to dataset when provided
        if attrgen_run_id is not None:
            try:
                from backend.infrastructure.storage.models import AttrGenerationRun

                r = AttrGenerationRun.get_by_id(int(attrgen_run_id))
                if int(r.dataset_id.id) != ds_id:
                    raise ValueError("attrgen_run_id gehört zu einem anderen Dataset")
            except Exception as e:
                return {"ok": False, "error": str(e)}
        _BENCH_PROGRESS[run_id] = {
            "status": "queued",
            "dataset_id": ds_id,
            "llm": llm,
            "batch_size": batch_size,
            "vllm_base_url": vllm_base_url,
            "vllm_api_key": vllm_api_key,
            "max_new_tokens": max_new_tokens,
            "scale_mode": scale_mode,
            "dual_fraction": (
                float(dual_fraction)
                if isinstance(dual_fraction, (int, float))
                else None
            ),
            "attrgen_run_id": (
                int(attrgen_run_id) if attrgen_run_id is not None else None
            ),
            "cancel_requested": False,
        }

    t = threading.Thread(target=_bench_run_background, args=(run_id,), daemon=True)
    t.start()
    # Start a lightweight poller to keep progress fresh during the run
    try:
        ds_id_int = int(ds_id)
        t_poll = threading.Thread(
            target=_bench_progress_poller, args=(run_id, ds_id_int), daemon=True
        )
        t_poll.start()
    except Exception:
        pass
    return {"ok": True, "run_id": run_id}


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
            if info:
                info.setdefault("status", _progress_status(info))
        except Exception:
            info = {"status": "unknown"}
    # Normalize status if incomplete
    try:
        d = int((info or {}).get("done") or 0)
        t = int((info or {}).get("total") or 0)
        if (t > 0 and d < t) and (info or {}).get("status") == "done":
            info["status"] = "partial"
    except Exception:
        pass
    if info and info.get("status") in (None, "unknown"):
        info["status"] = _progress_status(info)
    return {"ok": True, **(info or {})}


@router.post("/benchmarks/{run_id}/cancel")
def bench_cancel(run_id: int) -> dict:
    ensure_db()
    info = _BENCH_PROGRESS.get(run_id)
    if not info:
        raise HTTPException(
            status_code=404, detail="Benchmark-Run unbekannt oder bereits beendet"
        )
    state = info.get("status")
    if state not in {"queued", "running", "partial", "cancelling"}:
        raise HTTPException(
            status_code=400, detail=f"Benchmark ist nicht aktiv (Status: {state})"
        )
    if state == "cancelling":
        return {"ok": True}
    info["cancel_requested"] = True
    info["status"] = "cancelling"
    return {"ok": True}


@router.get("/datasets/{dataset_id}/benchmarks/active")
def active_benchmark(dataset_id: int) -> dict:
    ensure_db()
    ds_id = int(dataset_id)
    for run_id, info in list(_BENCH_PROGRESS.items()):
        if info.get("dataset_id") != ds_id:
            continue
        status = info.get("status", "unknown")
        if status not in {"queued", "running", "partial", "cancelling"}:
            continue
        try:
            _bench_update_progress(run_id, ds_id)
        except Exception:
            pass
        return {
            "ok": True,
            "active": True,
            "run_id": run_id,
            "status": info.get("status"),
            "done": info.get("done"),
            "total": info.get("total"),
            "pct": info.get("pct"),
            "error": info.get("error"),
        }
    return {"ok": True, "active": False}


@router.get("/runs/{run_id}/metrics")
def run_metrics(run_id: int) -> Dict[str, Any]:
    ensure_db()
    ck = _cache_key(run_id, "metrics", {"v": METRICS_CACHE_VERSION})
    cached = _cache_get(run_id, "metrics", ck)
    if cached:
        return cached
    df = _df_for_read(run_id)
    if df.empty:
        payload = {
            "ok": True,
            "n": 0,
            "hist": {"bins": [], "shares": []},
            "attributes": {},
        }
        _cache_put(run_id, "metrics", ck, payload)
        return payload
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
            {
                "category": str(r[col]),
                "count": int(r["count"]),
                "mean": float(r["mean"]),
            }
            for _, r in tab.iterrows()
        ]
        return {"categories": cats_meta, "baseline": base}

    attrs = {
        k: attr_meta(k)
        for k in [
            "gender",
            "origin_region",
            "religion",
            "sexuality",
            "marriage_status",
            "education",
        ]
    }
    cat_work = df.copy()
    if "trait_category" in cat_work.columns:
        tc_series = (
            cat_work["trait_category"].fillna(UNKNOWN_TRAIT_CATEGORY).astype(str)
        )
    else:
        tc_series = pd.Series(
            [UNKNOWN_TRAIT_CATEGORY] * len(cat_work), index=cat_work.index
        )
    cat_work["trait_category"] = tc_series
    cat_hists: List[Dict[str, Any]] = []
    for cat, sub in cat_work.groupby("trait_category"):
        seq = pd.to_numeric(sub["rating"], errors="coerce").dropna().astype(int)
        cat_counts = seq.value_counts().reindex(cats, fill_value=0).sort_index()
        total_cat = cat_counts.sum()
        cat_shares = (
            (cat_counts / total_cat).tolist() if total_cat > 0 else [0.0] * len(cats)
        )
        cat_hists.append(
            {
                "category": cat,
                "bins": [str(x) for x in cats],
                "counts": [int(x) for x in cat_counts.tolist()],
                "shares": cat_shares,
            }
        )
    cat_summary = (
        cat_work.groupby("trait_category")["rating"]
        .agg(["count", "mean", "std"])
        .reset_index()
        .rename(columns={"trait_category": "category"})
    )
    cat_summary_records = [
        {
            "category": str(r["category"]),
            "count": int(r["count"]),
            "mean": float(r["mean"]),
            "std": float(r["std"]) if r["std"] == r["std"] else None,
        }
        for _, r in cat_summary.iterrows()
    ]
    payload = {
        "ok": True,
        "n": int(len(df)),
        "hist": {
            "bins": [str(c) for c in cats],
            "shares": shares,
            "counts": [int(x) for x in counts.tolist()],
        },
        "trait_categories": {
            "histograms": cat_hists,
            "summary": cat_summary_records,
        },
        "attributes": attrs,
    }
    _cache_put(run_id, "metrics", ck, payload)
    return payload


@router.get("/runs/{run_id}/order-metrics")
def run_order_metrics(run_id: int) -> Dict[str, Any]:
    """Metrics for pairs asked in both directions (in vs. rev).

    Returns aggregate and per-case metrics based on normalised ratings where
    reversed answers are mapped to the normal direction already.
    """
    ensure_db()
    ck = _cache_key(run_id, "order", {})
    cached = _cache_get(run_id, "order", ck)
    if cached:
        return cached
    df = _df_for_read(run_id)
    if df.empty:
        payload = {
            "ok": True,
            "n_pairs": 0,
            "rma": {},
            "obe": {},
            "usage": {},
            "test_retest": {},
            "correlation": {},
            "by_case": [],
        }
        _cache_put(run_id, "order", ck, payload)
        return payload
    # Keep only rows with explicit scale_order
    if "scale_order" not in df.columns:
        return {
            "ok": True,
            "n_pairs": 0,
            "rma": {},
            "obe": {},
            "usage": {},
            "test_retest": {},
            "correlation": {},
            "by_case": [],
        }

    work = df.copy()
    # Build pairs by (persona, case)
    sub = work.loc[
        work["scale_order"].isin(["in", "rev"]) & work["rating"].notna(),
        ["persona_uuid", "case_id", "rating", "scale_order"],
    ]
    if sub.empty:
        return {
            "ok": True,
            "n_pairs": 0,
            "rma": {},
            "obe": {},
            "usage": {},
            "test_retest": {},
            "correlation": {},
            "by_case": [],
        }
    piv = sub.pivot_table(
        index=["persona_uuid", "case_id"],
        columns="scale_order",
        values="rating",
        aggfunc="first",
    ).reset_index()
    if not ("in" in piv.columns and "rev" in piv.columns):
        return {
            "ok": True,
            "n_pairs": 0,
            "rma": {},
            "obe": {},
            "usage": {},
            "test_retest": {},
            "correlation": {},
            "by_case": [],
        }
    pairs = piv.dropna(subset=["in", "rev"]).copy()
    if pairs.empty:
        return {
            "ok": True,
            "n_pairs": 0,
            "rma": {},
            "obe": {},
            "usage": {},
            "test_retest": {},
            "correlation": {},
            "by_case": [],
        }
    pairs["diff"] = pairs["in"].astype(float) - pairs["rev"].astype(float)
    pairs["abs_diff"] = pairs["diff"].abs()

    # RMA
    exact = float((pairs["abs_diff"] == 0).mean()) if len(pairs) else 0.0
    mae = float(pairs["abs_diff"].mean()) if len(pairs) else 0.0
    try:
        from backend.domain.analytics.benchmarks.analytics import mann_whitney_cliffs

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
    pear = (
        float(pairs["in"].corr(pairs["rev"], method="pearson"))
        if len(pairs) > 1
        else float("nan")
    )
    spear = (
        float(pairs["in"].corr(pairs["rev"], method="spearman"))
        if len(pairs) > 1
        else float("nan")
    )
    try:
        import scipy.stats as ss  # type: ignore

        kend = float(ss.kendalltau(pairs["in"], pairs["rev"]).correlation)
    except Exception:
        kend = float("nan")

    # Per-case breakdown
    rows: List[Dict[str, Any]] = []
    try:
        trait_map = {}
        trait_cat_map = {}
        for r in Trait.select():
            trait_map[str(r.id)] = r.adjective or str(r.id)
            trait_cat_map[str(r.id)] = r.category or UNKNOWN_TRAIT_CATEGORY
    except Exception:
        trait_map = {}
        trait_cat_map = {}
    for k, g in pairs.groupby("case_id"):
        ad = float((g["abs_diff"] == 0).mean()) if len(g) else 0.0
        rows.append(
            {
                "case_id": str(k),
                "adjective": trait_map.get(str(k)),
                "trait_category": trait_cat_map.get(str(k)) or UNKNOWN_TRAIT_CATEGORY,
                "n_pairs": int(len(g)),
                "exact_rate": ad,
                "mae": float(g["abs_diff"].mean()) if len(g) else 0.0,
            }
        )
    by_cat = []
    cat_stats: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        cat = r.get("trait_category") or UNKNOWN_TRAIT_CATEGORY
        entry = cat_stats.setdefault(
            cat, {"trait_category": cat, "n_pairs": 0, "exact_sum": 0.0, "mae_sum": 0.0}
        )
        n_pairs_case = int(r.get("n_pairs") or 0)
        entry["n_pairs"] += n_pairs_case
        entry["exact_sum"] += float(r.get("exact_rate") or 0.0) * n_pairs_case
        entry["mae_sum"] += float(r.get("mae") or 0.0) * n_pairs_case
    for cat, stat in cat_stats.items():
        n_pairs_cat = stat["n_pairs"] or 0
        if n_pairs_cat <= 0:
            continue
        by_cat.append(
            {
                "trait_category": cat,
                "n_pairs": n_pairs_cat,
                "exact_rate": stat["exact_sum"] / n_pairs_cat,
                "mae": stat["mae_sum"] / n_pairs_cat,
            }
        )

    payload = {
        "ok": True,
        "n_pairs": int(len(pairs)),
        "rma": {"exact_rate": exact, "mae": mae, "cliffs_delta": cliffs},
        "obe": {"mean_diff": mu, "ci_low": ci_low, "ci_high": ci_high, "sd": sd},
        "usage": {"eei": eei, "mni": mni, "sv": sv},
        "test_retest": {"within1_rate": within1, "mean_abs_diff": mean_abs},
        "correlation": {"pearson": pear, "spearman": spear, "kendall": kend},
        "by_case": rows,
        "by_trait_category": by_cat,
    }
    _cache_put(run_id, "order", ck, payload)
    return payload


@router.get("/runs/{run_id}/missing")
def run_missing(run_id: int) -> Dict[str, Any]:
    """Return count of missing BenchmarkResult pairs and a small sample.

    Missing = all (persona in dataset) × (traits) that have no BenchmarkResult for this run.
    Uses a SQL anti-join for efficiency.
    """
    ensure_db()
    from backend.infrastructure.storage.db import get_db

    db = get_db()
    rec = BenchmarkRun.get_or_none(BenchmarkRun.id == run_id)
    if not rec:
        return {"ok": False, "error": "run_not_found"}
    dataset_id = int(rec.dataset_id.id)

    # Total expected pairs and done
    traits_n = TraitRepository().count()
    from backend.infrastructure.storage.models import DatasetPersona

    personas_n = (
        DatasetPersona.select().where(DatasetPersona.dataset_id == dataset_id).count()
    )
    total = personas_n * traits_n
    done = (
        BenchmarkResult.select(BenchmarkResult.persona_uuid_id, BenchmarkResult.case_id)
        .where(BenchmarkResult.benchmark_run_id == run_id)
        .distinct()
        .count()
    )

    MAX_DIRECT_SCAN = 500_000
    skip_heavy_scan = bool(total and total > MAX_DIRECT_SCAN)
    missing = max(0, (total or 0) - (done or 0))
    samples: List[Dict[str, Any]] = []
    sampling_limited = skip_heavy_scan
    if not skip_heavy_scan:
        trait_alias = Trait.alias()
        try:
            cnt_query = (
                DatasetPersona.select(pw.fn.COUNT(1))
                .join(trait_alias, pw.JOIN.CROSS)
                .switch(DatasetPersona)
                .join(
                    BenchmarkResult,
                    pw.JOIN.LEFT_OUTER,
                    on=(
                        (BenchmarkResult.benchmark_run_id == run_id)
                        & (BenchmarkResult.persona_uuid_id == DatasetPersona.persona_id)
                        & (BenchmarkResult.case_id == trait_alias.id)
                    ),
                )
                .where(
                    (DatasetPersona.dataset_id == dataset_id)
                    & (BenchmarkResult.id.is_null(True))
                )
            )
            missing = int(cnt_query.scalar() or 0)
        except Exception:
            missing = max(0, (total or 0) - (done or 0))

        try:
            sample_query = (
                DatasetPersona.select(
                    DatasetPersona.persona_id,
                    trait_alias.id.alias("case_id"),
                    trait_alias.adjective.alias("adjective"),
                )
                .join(trait_alias, pw.JOIN.CROSS)
                .switch(DatasetPersona)
                .join(
                    BenchmarkResult,
                    pw.JOIN.LEFT_OUTER,
                    on=(
                        (BenchmarkResult.benchmark_run_id == run_id)
                        & (BenchmarkResult.persona_uuid_id == DatasetPersona.persona_id)
                        & (BenchmarkResult.case_id == trait_alias.id)
                    ),
                )
                .where(
                    (DatasetPersona.dataset_id == dataset_id)
                    & (BenchmarkResult.id.is_null(True))
                )
                .limit(20)
                .tuples()
            )
            for pid, cid, adj in sample_query:
                samples.append(
                    {
                        "persona_uuid": str(pid),
                        "case_id": str(cid),
                        "adjective": str(adj) if adj is not None else None,
                    }
                )
        except Exception:
            samples = []

    return {
        "ok": True,
        "dataset_id": dataset_id,
        "total": total,
        "done": done,
        "missing": missing,
        "samples": samples,
        "sampling_limited": sampling_limited,
    }


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
    trait_category: Optional[str] = Query(None),
) -> Dict[str, Any]:
    ensure_db()
    ck = _cache_key(
        run_id,
        "deltas",
        {
            "attribute": attribute,
            "baseline": baseline,
            "n_perm": int(n_perm),
            "alpha": float(alpha),
            "trait_category": trait_category,
        },
    )
    cached = _cache_get(run_id, "deltas", ck)
    if cached:
        return cached
    df = _filter_by_trait_category(_df_for_read(run_id), trait_category)
    if df.empty or attribute not in df.columns:
        payload = {"ok": True, "n": 0, "rows": []}
        _cache_put(run_id, "deltas", ck, payload)
        return payload
    result = bench_ana.build_deltas_payload(
        df, attribute, baseline=baseline, n_perm=n_perm, alpha=alpha
    )
    payload = {"ok": True, **result}
    _cache_put(run_id, "deltas", ck, payload)
    return payload


@router.get("/runs/{run_id}/means")
def run_means(
    run_id: int,
    attribute: str,
    top_n: Optional[int] = None,
    trait_category: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Mean rating and counts per category for a given attribute."""
    ensure_db()
    ck = _cache_key(
        run_id,
        "means",
        {"attribute": attribute, "top_n": top_n, "trait_category": trait_category},
    )
    cached = _cache_get(run_id, "means", ck)
    if cached:
        return cached
    import pandas as pd

    df = _df_for_read(run_id)
    if df.empty or attribute not in df.columns:
        payload = {"ok": True, "rows": []}
        _cache_put(run_id, "means", ck, payload)
        return payload
    work = _filter_by_trait_category(df, trait_category)
    if work.empty:
        payload = {"ok": True, "rows": []}
        _cache_put(run_id, "means", ck, payload)
        return payload
    work = work.copy()
    work[attribute] = work[attribute].fillna("Unknown").astype(str)
    s = pd.to_numeric(work["rating"], errors="coerce")
    g = work.assign(r=s).groupby(attribute)["r"].agg(["count", "mean"]).reset_index()
    g = g.sort_values("count", ascending=False)
    if top_n and top_n > 0:
        g = g.head(int(top_n))
    rows = [
        {
            "category": str(r[attribute]),
            "count": int(r["count"]),
            "mean": float(r["mean"]),
        }
        for _, r in g.iterrows()
    ]
    payload = {"ok": True, "rows": rows}
    _cache_put(run_id, "means", ck, payload)
    return payload


@router.get("/runs/{run_id}/forest")
def run_forest(
    run_id: int,
    attribute: str,
    baseline: Optional[str] = None,
    target: Optional[str] = None,
    min_n: int = 1,
    trait_category: Optional[str] = Query(None),
) -> Dict[str, Any]:
    ensure_db()
    ck = _cache_key(
        run_id,
        "forest",
        {
            "attribute": attribute,
            "baseline": baseline,
            "target": target,
            "min_n": int(min_n),
            "trait_category": trait_category,
        },
    )
    cached = _cache_get(run_id, "forest", ck)
    if cached:
        return cached
    df = _filter_by_trait_category(_df_for_read(run_id), trait_category)
    if df.empty or attribute not in df.columns:
        payload = {"ok": True, "n": 0, "rows": []}
        _cache_put(run_id, "forest", ck, payload)
        return payload

    import numpy as np
    import pandas as pd

    work = df.copy()
    work[attribute] = work[attribute].fillna("Unknown").astype(str)
    if baseline is None:
        s = work.groupby(attribute)["rating"].size().sort_values(ascending=False)
        baseline = str(s.index[0]) if not s.empty else "Unknown"
    if target is None:
        s2 = (
            work.loc[work[attribute] != baseline]
            .groupby(attribute)["rating"]
            .size()
            .sort_values(ascending=False)
        )
        target = str(s2.index[0]) if not s2.empty else None

    agg = (
        work.groupby(["case_id", "trait_category", attribute])["rating"]
        .agg(count="count", mean="mean", std="std")
        .reset_index()
    )
    agg = agg.loc[agg["case_id"].astype(str).str.startswith("g")]
    if agg.empty:
        payload = {"ok": True, "n": 0, "rows": []}
        _cache_put(run_id, "forest", ck, payload)
        return payload
    baseline_df = agg.loc[agg[attribute] == baseline].set_index(
        ["case_id", "trait_category"]
    )
    if baseline_df.empty:
        payload = {"ok": True, "n": 0, "rows": []}
        _cache_put(run_id, "forest", ck, payload)
        return payload
    rows_list: List[Dict[str, Any]] = []
    cats = (
        [target]
        if target is not None
        else [
            c
            for c in agg[attribute].dropna().unique().tolist()
            if str(c) != str(baseline)
        ]
    )
    cats = [c for c in cats if c is not None]
    for cat in cats:
        cat_df = agg.loc[agg[attribute] == cat].set_index(["case_id", "trait_category"])
        merged = (
            baseline_df.join(
                cat_df,
                how="inner",
                lsuffix="_base",
                rsuffix="_cat",
            )
            .reset_index()
            .rename(columns={"index": "case_id"})
        )
        if merged.empty:
            continue
        merged = merged.loc[
            (merged["count_base"] >= min_n) & (merged["count_cat"] >= min_n)
        ].copy()
        if merged.empty:
            continue
        merged["delta"] = merged["mean_cat"] - merged["mean_base"]
        merged["se"] = np.sqrt(
            (merged["std_base"] ** 2) / merged["count_base"]
            + (merged["std_cat"] ** 2) / merged["count_cat"]
        )
        se_mask = (merged["count_base"] > 1) & (merged["count_cat"] > 1)
        merged.loc[~se_mask, "se"] = np.nan
        merged["ci_low"] = merged["delta"] - 1.96 * merged["se"]
        merged["ci_high"] = merged["delta"] + 1.96 * merged["se"]
        for row in merged.itertuples(index=False):
            rows_list.append(
                {
                    "case_id": str(row.case_id),
                    "category": str(cat),
                    "baseline": str(baseline),
                    "trait_category": str(row.trait_category),
                    "n_base": int(row.count_base),
                    "n_cat": int(row.count_cat),
                    "delta": (
                        float(row.delta) if row.delta == row.delta else float("nan")
                    ),
                    "se": float(row.se) if row.se == row.se else None,
                    "ci_low": float(row.ci_low) if row.ci_low == row.ci_low else None,
                    "ci_high": (
                        float(row.ci_high) if row.ci_high == row.ci_high else None
                    ),
                }
            )

    labels_map: Dict[str, str] = {str(c.id): str(c.adjective) for c in Trait.select()}
    for r in rows_list:
        r["label"] = labels_map.get(r["case_id"], r["case_id"])

    if rows_list:
        arr = pd.DataFrame(rows_list)
        if arr["se"].notna().any():
            sub = arr.loc[arr["se"].notna()].copy()
            w = 1.0 / (sub["se"] ** 2)
            w = w.replace([np.inf, -np.inf], np.nan).fillna(0.0)
            mu = (
                float(np.nansum(w * sub["delta"]) / np.nansum(w))
                if np.nansum(w) > 0
                else float("nan")
            )
            se_mu = (
                float(np.sqrt(1.0 / np.nansum(w))) if np.nansum(w) > 0 else float("nan")
            )
            overall = {
                "mean": mu if np.isfinite(mu) else None,
                "ci_low": mu - 1.96 * se_mu if np.isfinite(se_mu) else None,
                "ci_high": mu + 1.96 * se_mu if np.isfinite(se_mu) else None,
            }
        else:
            overall = {"mean": None, "ci_low": None, "ci_high": None}
    else:
        overall = {"mean": None, "ci_low": None, "ci_high": None}

    rows_list.sort(
        key=lambda r: (
            r["delta"] if (r["delta"] == r["delta"]) else float("inf"),
            (r.get("label") or r["case_id"]),
        )
    )
    payload = {"ok": True, "n": len(rows_list), "rows": rows_list, "overall": overall}
    _cache_put(run_id, "forest", ck, payload)
    return payload


def _warm_job_snapshot(run_id: int, job: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not job:
        return {
            "ok": True,
            "run_id": int(run_id),
            "status": "idle",
            "steps": [],
            "started_at": None,
            "updated_at": None,
            "finished_at": None,
            "duration_ms": None,
            "current_step": None,
            "had_errors": False,
            "error": None,
        }
    snap = copy.deepcopy(job)
    snap["ok"] = True
    snap.setdefault("steps", [])
    snap.setdefault("error", None)
    snap.setdefault("had_errors", False)
    return snap


def _start_warm_cache_job(run_id: int) -> Dict[str, Any]:
    ensure_db()
    now = utcnow().isoformat()
    with _WARM_CACHE_LOCK:
        existing = _WARM_CACHE_JOBS.get(run_id)
        if existing and existing.get("status") == "running":
            return copy.deepcopy(existing)
        job = {
            "run_id": int(run_id),
            "status": "running",
            "started_at": now,
            "updated_at": now,
            "finished_at": None,
            "duration_ms": None,
            "current_step": None,
            "steps": [],
            "had_errors": False,
        }
        _WARM_CACHE_JOBS[run_id] = job
    thread = threading.Thread(
        target=_warm_cache_worker,
        args=(run_id,),
        daemon=True,
        name=f"warm-cache-{run_id}",
    )
    thread.start()
    return copy.deepcopy(job)


def _warm_cache_worker(run_id: int) -> None:
    job = _WARM_CACHE_JOBS.get(run_id)
    if not job:
        return
    started = time.time()
    _LOG.info("[warm-cache:%s] worker started", run_id)
    try:
        ensure_db()
        try:
            db = get_db()
            ctx = db.connection_context()
        except Exception:
            ctx = nullcontext()
        metrics_payload: Dict[str, Any] = {}
        with ctx:
            metrics_payload = _run_warm_step(job, "metrics", run_metrics, run_id) or {}
            _run_warm_step(job, "missing", run_missing, run_id)
            _run_warm_step(job, "order_metrics", run_order_metrics, run_id)
            for attr in _DEFAULT_ANALYSIS_ATTRIBUTES:
                _run_warm_step(job, f"means:{attr}", run_means, run_id, attr)
                _run_warm_step(job, f"deltas:{attr}", run_deltas, run_id, attr)

            attr_info = (
                metrics_payload.get("attributes")
                if isinstance(metrics_payload, dict)
                else {}
            ) or {}
            focus_attr = "gender"
            focus_meta = attr_info.get(focus_attr) or {}
            focus_baseline = focus_meta.get("baseline")
            if focus_baseline:
                _run_warm_step(
                    job,
                    f"deltas:{focus_attr}:{focus_baseline}",
                    run_deltas,
                    run_id,
                    focus_attr,
                    focus_baseline,
                )
            focus_targets = [
                cat.get("category")
                for cat in (focus_meta.get("categories") or [])
                if cat.get("category") and cat.get("category") != focus_baseline
            ]
            focus_target = focus_targets[0] if focus_targets else None
            _run_warm_step(
                job,
                f"forest:{focus_attr}",
                run_forest,
                run_id,
                focus_attr,
                focus_baseline,
                focus_target,
                1,
            )
    except Exception as exc:  # pragma: no cover - best-effort diagnostics
        job["status"] = "error"
        job["error"] = str(exc)
        _LOG.exception("[warm-cache:%s] worker failed: %s", run_id, exc)
    finally:
        job["duration_ms"] = int((time.time() - started) * 1000)
        finished = utcnow().isoformat()
        job["finished_at"] = finished
        job["updated_at"] = finished
        job["current_step"] = None
        if job.get("status") == "running":
            job["status"] = "done_with_errors" if job.get("had_errors") else "done"
        _LOG.info(
            "[warm-cache:%s] worker finished status=%s duration_ms=%s",
            run_id,
            job.get("status"),
            job.get("duration_ms"),
        )


def _run_warm_step(job: Dict[str, Any], label: str, fn, *args, **kwargs):
    step = {
        "name": label,
        "status": "running",
        "ok": None,
        "started_at": utcnow().isoformat(),
        "finished_at": None,
        "duration_ms": None,
        "error": None,
    }
    job["steps"].append(step)
    job["current_step"] = label
    job["updated_at"] = step["started_at"]
    t0 = time.time()
    run_id = job.get("run_id")
    _LOG.info("[warm-cache:%s] step %s started", run_id, label)
    try:
        result = fn(*args, **kwargs)
        step["status"] = "done"
        step["ok"] = True
        step["duration_ms"] = int((time.time() - t0) * 1000)
        step["finished_at"] = utcnow().isoformat()
        _LOG.info(
            "[warm-cache:%s] step %s finished ok duration_ms=%s",
            run_id,
            label,
            step["duration_ms"],
        )
        return result
    except Exception as exc:
        step["status"] = "error"
        step["ok"] = False
        step["error"] = str(exc)
        step["duration_ms"] = int((time.time() - t0) * 1000)
        step["finished_at"] = utcnow().isoformat()
        job["had_errors"] = True
        _LOG.exception(
            "[warm-cache:%s] step %s failed: %s", run_id, label, exc, exc_info=exc
        )
        return None
    finally:
        job["current_step"] = None
        job["updated_at"] = utcnow().isoformat()


@router.post("/runs/{run_id}/warm-cache")
def warm_run_cache(run_id: int) -> Dict[str, Any]:
    """Start (or return) the asynchronous warm-cache job for a run."""
    job = _start_warm_cache_job(run_id)
    return {"ok": True, **job}


@router.get("/runs/{run_id}/warm-cache")
def warm_run_cache_status(run_id: int) -> Dict[str, Any]:
    """Return current warm-cache job progress."""
    job = _WARM_CACHE_JOBS.get(run_id)
    return _warm_job_snapshot(run_id, job)
