from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from backend.domain.analytics.benchmarks.analytics import (
    BenchQuery,
    load_benchmark_dataframe,
)
from backend.infrastructure.storage.models import (
    BenchmarkResult,
    BenchmarkRun,
    CounterfactualLink,
    Model,
)

from ..deps import db_session
from ..utils import ensure_db

router = APIRouter(tags=["metrics"], dependencies=[Depends(db_session)])


@router.get("/metrics/benchmark-distribution")
def benchmark_distribution(
    dataset_ids: Optional[List[int]] = Query(default=None),
    models: Optional[List[str]] = Query(default=None),
    case_ids: Optional[List[str]] = Query(default=None),
    rationale: Optional[bool] = Query(default=None),
) -> Dict[str, Any]:
    ensure_db()
    cfg = BenchQuery(
        dataset_ids=tuple(dataset_ids) if dataset_ids else None,
        model_names=tuple(models) if models else None,
        case_ids=tuple(case_ids) if case_ids else None,
        include_rationale=rationale,
        run_ids=None,
    )
    df = load_benchmark_dataframe(cfg)
    if df.empty:
        return {
            "ok": True,
            "n": 0,
            "hist": {"bins": [], "shares": []},
            "per_category": {},
        }
    s = df["rating"].dropna().astype(int)
    cats = list(range(int(s.min()), int(s.max()) + 1))
    counts = s.value_counts().reindex(cats, fill_value=0).sort_index()
    shares = (counts / counts.sum()).tolist()

    def cat_mean(col: str):
        if col not in df.columns:
            return []
        g = df[[col, "rating"]].dropna(subset=["rating"]).copy()
        g[col] = g[col].fillna("Unknown")
        agg = g.groupby(col)["rating"].agg(["count", "mean"]).reset_index()
        agg = agg.sort_values("count", ascending=False)
        return [
            {
                "category": str(r[col]),
                "count": int(r["count"]),
                "mean": float(r["mean"]),
            }
            for _, r in agg.iterrows()
        ]

    per_category = {
        "gender": cat_mean("gender"),
        "origin_region": cat_mean("origin_region"),
        "religion": cat_mean("religion"),
        "sexuality": cat_mean("sexuality"),
        "marriage_status": cat_mean("marriage_status"),
        "education": cat_mean("education"),
    }
    return {
        "ok": True,
        "n": int(len(df)),
        "hist": {"bins": cats, "shares": shares},
        "per_category": per_category,
    }


@router.get("/metrics/cf-deltas")
def counterfactual_deltas(
    dataset_id: int,
    models: Optional[List[str]] = Query(default=None),
    case_ids: Optional[List[str]] = Query(default=None),
    rationale: Optional[bool] = Query(default=None),
    attribute: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    ensure_db()
    links_q = CounterfactualLink.select().where(
        CounterfactualLink.dataset_id == dataset_id
    )
    if attribute:
        links_q = links_q.where(CounterfactualLink.changed_attribute == attribute)
    links = list(links_q)
    if not links:
        return {"ok": True, "n_pairs": 0, "overall": {}, "per_direction": []}

    src_ids = {str(l.source_persona_id) for l in links}
    cf_ids = {str(l.cf_persona_id) for l in links}

    br_src = (
        BenchmarkResult.select(
            BenchmarkResult.persona_uuid_id.alias("persona_uuid"),
            BenchmarkResult.case_id,
            Model.name.alias("model_name"),
            BenchmarkResult.rating,
            BenchmarkResult.benchmark_run_id.alias("run_id"),
            BenchmarkRun.include_rationale,
        )
        .join(BenchmarkRun, on=(BenchmarkResult.benchmark_run_id == BenchmarkRun.id))
        .join(Model, on=(BenchmarkRun.model_id == Model.id))
        .where(BenchmarkResult.persona_uuid_id.in_(list(src_ids)))
    )
    br_cf = (
        BenchmarkResult.select(
            BenchmarkResult.persona_uuid_id.alias("persona_uuid"),
            BenchmarkResult.case_id,
            Model.name.alias("model_name"),
            BenchmarkResult.rating,
            BenchmarkResult.benchmark_run_id.alias("run_id"),
            BenchmarkRun.include_rationale,
        )
        .join(BenchmarkRun, on=(BenchmarkResult.benchmark_run_id == BenchmarkRun.id))
        .join(Model, on=(BenchmarkRun.model_id == Model.id))
        .where(BenchmarkResult.persona_uuid_id.in_(list(cf_ids)))
    )
    if models:
        br_src = br_src.where(Model.name.in_(list(models)))
        br_cf = br_cf.where(Model.name.in_(list(models)))
    if case_ids:
        br_src = br_src.where(BenchmarkResult.case_id.in_(list(case_ids)))
        br_cf = br_cf.where(BenchmarkResult.case_id.in_(list(case_ids)))
    if rationale is not None:
        br_src = br_src.where(BenchmarkRun.include_rationale == bool(rationale))
        br_cf = br_cf.where(BenchmarkRun.include_rationale == bool(rationale))

    src_map: Dict[tuple, float] = {}
    for r in br_src.dicts():
        key = (
            str(r["persona_uuid"]),
            str(r["case_id"]),
            int(r["run_id"]) if r["run_id"] is not None else -1,
            str(r["model_name"]),
        )
        src_map[key] = float(r["rating"]) if r["rating"] is not None else float("nan")
    cf_map: Dict[tuple, float] = {}
    for r in br_cf.dicts():
        key = (
            str(r["persona_uuid"]),
            str(r["case_id"]),
            int(r["run_id"]) if r["run_id"] is not None else -1,
            str(r["model_name"]),
        )
        cf_map[key] = float(r["rating"]) if r["rating"] is not None else float("nan")

    deltas: List[float] = []
    per_dir: Dict[str, List[float]] = {}
    for l in links:
        src_uuid = str(l.source_persona)
        cf_uuid = str(l.cf_persona)
        for (p, case, run, model), y_src in src_map.items():
            if p != src_uuid:
                continue
            y_cf = cf_map.get((cf_uuid, case, run, model))
            if y_cf is None:
                continue
            d = float(y_cf) - float(y_src)
            deltas.append(d)
            dir_key = f"{l.changed_attribute} {l.from_value}→{l.to_value}"
            per_dir.setdefault(dir_key, []).append(d)

    if not deltas:
        return {"ok": True, "n_pairs": 0, "overall": {}, "per_direction": []}

    def _stats(xs: List[float]) -> Dict[str, Any]:
        a = [x for x in xs if x == x]
        if not a:
            return {"n": 0, "mean": None, "std": None}
        import math

        n = len(a)
        mu = sum(a) / n
        var = sum((x - mu) ** 2 for x in a) / (n - 1) if n > 1 else 0.0
        return {"n": n, "mean": mu, "std": math.sqrt(var)}

    per_direction = [{"direction": k, **_stats(v)} for k, v in per_dir.items()]
    per_direction.sort(key=lambda r: abs(r.get("mean") or 0), reverse=True)

    return {
        "ok": True,
        "n_pairs": len(deltas),
        "overall": _stats(deltas),
        "per_direction": per_direction[:50],
    }
