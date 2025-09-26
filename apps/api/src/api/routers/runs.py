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

