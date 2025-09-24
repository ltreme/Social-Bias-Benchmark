from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Query
from pydantic import BaseModel

# Ensure project root (with 'apps') is importable
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from shared.storage.db import init_database, create_tables, get_db
from shared.storage.models import (
    Dataset,
    DatasetPersona,
    BenchmarkRun,
    BenchmarkResult,
    Persona,
    Country,
    CounterfactualLink,
    Model,
)

from analysis.benchmarks.analytics import BenchQuery, load_benchmark_dataframe
from fastapi.middleware.cors import CORSMiddleware


def ensure_db() -> None:
    init_database(os.getenv("DB_URL"))
    create_tables()


app = FastAPI(title="SBB API", version="0.1.0")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # evtl. weitere Hosts/IPs deiner Dev-Umgebung
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # kein "*" wenn Credentials!
    allow_credentials=True,           # nur wenn Cookies/Authorization genutzt werden
    allow_methods=["GET","POST","PUT","DELETE","OPTIONS"],
    allow_headers=["*"],              # oder explizit: "Content-Type","Authorization",...
    expose_headers=["Content-Disposition"],  # falls du Custom-Header im Client lesen willst
)


class DatasetOut(BaseModel):
    id: int
    name: str
    kind: str
    size: int


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/datasets", response_model=List[DatasetOut])
def list_datasets() -> List[DatasetOut]:
    ensure_db()
    out: List[DatasetOut] = []
    for ds in Dataset.select():
        n = DatasetPersona.select().where(DatasetPersona.dataset_id == ds.id).count()
        out.append(DatasetOut(id=ds.id, name=ds.name, kind=ds.kind, size=n))
    return out


class RunOut(BaseModel):
    id: int
    model_name: str
    include_rationale: bool
    dataset_id: Optional[int]
    created_at: str


@app.get("/runs", response_model=List[RunOut])
def list_runs() -> List[RunOut]:
    ensure_db()
    out: List[RunOut] = []
    for r in BenchmarkRun.select().join(Model).order_by(BenchmarkRun.id.desc()):
        out.append(
            RunOut(
                id=r.id,
                model_name=r.model_id.name,
                include_rationale=bool(r.include_rationale),
                dataset_id=int(r.dataset_id.id) if r.dataset_id else None,
                created_at=str(r.created_at),
            )
        )
    return out


@app.get("/metrics/benchmark-distribution")
def benchmark_distribution(
    dataset_ids: Optional[List[int]] = Query(default=None),
    models: Optional[List[str]] = Query(default=None),
    case_ids: Optional[List[str]] = Query(default=None),
    rationale: Optional[bool] = Query(default=None),
) -> Dict[str, Any]:
    """Return rating distribution and simple per-category means."""
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
        return {"ok": True, "n": 0, "hist": {"bins": [], "shares": []}, "per_category": {}}
    # Rating histogram 1..5
    s = df["rating"].dropna().astype(int)
    cats = list(range(int(s.min()), int(s.max()) + 1))
    counts = s.value_counts().reindex(cats, fill_value=0).sort_index()
    shares = (counts / counts.sum()).tolist()

    def cat_mean(col: str) -> List[Dict[str, Any]]:
        if col not in df.columns:
            return []
        g = (
            df[[col, "rating"]].dropna(subset=["rating"]).copy()
        )
        g[col] = g[col].fillna("Unknown")
        agg = g.groupby(col)["rating"].agg(["count", "mean"]).reset_index()
        agg = agg.sort_values("count", ascending=False)
        return [
            {"category": str(r[col]), "count": int(r["count"]), "mean": float(r["mean"])}
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
    
@app.get("/models")
def list_models() -> List[str]:
    ensure_db()
    return [m.name for m in Model.select()]


@app.get("/metrics/cf-deltas")
def counterfactual_deltas(
    dataset_id: int,
    models: Optional[List[str]] = Query(default=None),
    case_ids: Optional[List[str]] = Query(default=None),
    rationale: Optional[bool] = Query(default=None),
    attribute: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Return paired source->cf deltas summary for a counterfactual dataset."""
    ensure_db()
    # Collect links
    links_q = CounterfactualLink.select()
    links_q = links_q.where(CounterfactualLink.dataset_id == dataset_id)
    if attribute:
        links_q = links_q.where(CounterfactualLink.changed_attribute == attribute)
    links = list(links_q)
    if not links:
        return {"ok": True, "n_pairs": 0, "overall": {}, "per_direction": []}

    src_ids = {str(l.source_persona_id) for l in links}
    cf_ids = {str(l.cf_persona_id) for l in links}

    br_src = BenchmarkResult.select(
        BenchmarkResult.persona_uuid_id.alias('persona_uuid'),
        BenchmarkResult.case_id,
        Model.name.alias('model_name'),
        BenchmarkResult.rating,
        BenchmarkResult.benchmark_run_id.alias('run_id'),
        BenchmarkRun.include_rationale,
    ).join(BenchmarkRun, on=(BenchmarkResult.benchmark_run_id == BenchmarkRun.id)).join(Model, on=(BenchmarkRun.model_id == Model.id)).where(
        BenchmarkResult.persona_uuid_id.in_(list(src_ids))
    )
    br_cf = BenchmarkResult.select(
        BenchmarkResult.persona_uuid_id.alias('persona_uuid'),
        BenchmarkResult.case_id,
        Model.name.alias('model_name'),
        BenchmarkResult.rating,
        BenchmarkResult.benchmark_run_id.alias('run_id'),
        BenchmarkRun.include_rationale,
    ).join(BenchmarkRun, on=(BenchmarkResult.benchmark_run_id == BenchmarkRun.id)).join(Model, on=(BenchmarkRun.model_id == Model.id)).where(
        BenchmarkResult.persona_uuid_id.in_(list(cf_ids))
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
        key = (str(r['persona_uuid']), str(r['case_id']), int(r['run_id']) if r['run_id'] is not None else -1, str(r['model_name']))
        src_map[key] = float(r['rating']) if r['rating'] is not None else float('nan')
    cf_map: Dict[tuple, float] = {}
    for r in br_cf.dicts():
        key = (str(r['persona_uuid']), str(r['case_id']), int(r['run_id']) if r['run_id'] is not None else -1, str(r['model_name']))
        cf_map[key] = float(r['rating']) if r['rating'] is not None else float('nan')

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

    per_direction = [
        {"direction": k, **_stats(v)} for k, v in per_dir.items()
    ]
    per_direction.sort(key=lambda r: abs(r.get("mean") or 0), reverse=True)

    return {
        "ok": True,
        "n_pairs": len(deltas),
        "overall": _stats(deltas),
        "per_direction": per_direction[:50],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8765, reload=True)

