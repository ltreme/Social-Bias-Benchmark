"""Benchmark runs API router - simplified to pure routing logic."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.application.services.benchmark_service import BenchmarkService

from ..deps import db_session
from ..utils import ensure_db

router = APIRouter(tags=["runs"], dependencies=[Depends(db_session)])


def _get_service() -> BenchmarkService:
    """Get benchmark service instance."""
    ensure_db()
    return BenchmarkService()


@router.get("/runs")
def list_runs() -> List[Dict[str, Any]]:
    """List all benchmark runs."""
    return _get_service().list_runs()


@router.get("/runs/{run_id}")
def get_run(run_id: int) -> Dict[str, Any]:
    """Get details of a specific benchmark run."""
    return _get_service().get_run(run_id)


@router.get("/models")
def list_models() -> List[str]:
    """List all available models."""
    return _get_service().list_models()


@router.post("/benchmarks/start")
def start_benchmark(body: dict) -> dict:
    """Start a benchmark run for a dataset with a given model.

    Body: {
        dataset_id: int,
        model_name: str,
        include_rationale?: bool,
        llm?: 'vllm'|'fake',
        batch_size?: int,
        vllm_base_url?: str,
        vllm_api_key?: str,
        attrgen_run_id?: int,
        max_new_tokens?: int,
        max_attempts?: int,
        system_prompt?: str,
        scale_mode?: 'in'|'rev'|'random50',
        dual_fraction?: float,
        resume_run_id?: int
    }
    """
    try:
        return _get_service().start_benchmark(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/benchmarks/{run_id}/status")
def bench_status(run_id: int) -> dict:
    """Get status of a benchmark run."""
    return _get_service().get_status(run_id)


@router.post("/benchmarks/{run_id}/cancel")
def bench_cancel(run_id: int) -> dict:
    """Cancel a running benchmark."""
    result = _get_service().cancel_benchmark(run_id)
    if not result.get("ok"):
        raise HTTPException(
            status_code=400, detail=result.get("error", "Unknown error")
        )
    return result


@router.get("/datasets/{dataset_id}/benchmarks/active")
def active_benchmark(dataset_id: int) -> dict:
    """Get active benchmark for a dataset."""
    return _get_service().get_active_benchmark(dataset_id)


@router.get("/runs/{run_id}/metrics")
def run_metrics(run_id: int) -> Dict[str, Any]:
    """Get comprehensive metrics for a benchmark run."""
    return _get_service().get_metrics(run_id)


@router.get("/runs/{run_id}/order-metrics")
def run_order_metrics(run_id: int) -> Dict[str, Any]:
    """Get order effect metrics (in vs. rev)."""
    return _get_service().get_order_metrics(run_id)


@router.get("/runs/{run_id}/missing")
def run_missing(run_id: int) -> Dict[str, Any]:
    """Get count and sample of missing benchmark results."""
    return _get_service().get_missing(run_id)


@router.delete("/runs/{run_id}")
def delete_run(run_id: int) -> Dict[str, Any]:
    """Delete a benchmark run and all associated results."""
    return _get_service().delete_run(run_id)


@router.get("/runs/{run_id}/deltas")
def run_deltas(
    run_id: int,
    attribute: str,
    baseline: Optional[str] = None,
    n_perm: int = 1000,
    alpha: float = 0.05,
    trait_category: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Get delta analysis for an attribute."""
    return _get_service().get_deltas(
        run_id, attribute, baseline, n_perm, alpha, trait_category
    )


@router.get("/runs/{run_id}/means")
def run_means(
    run_id: int,
    attribute: str,
    top_n: Optional[int] = None,
    trait_category: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Get mean ratings per category for a given attribute."""
    return _get_service().get_means(run_id, attribute, top_n, trait_category)


@router.get("/runs/{run_id}/forest")
def run_forest(
    run_id: int,
    attribute: str,
    baseline: Optional[str] = None,
    target: Optional[str] = None,
    min_n: int = 1,
    trait_category: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Get forest plot data for attribute comparisons."""
    return _get_service().get_forest(
        run_id, attribute, baseline, target, min_n, trait_category
    )


@router.post("/runs/{run_id}/warm-cache")
def warm_run_cache(run_id: int) -> Dict[str, Any]:
    """Start asynchronous cache warming job for a run."""
    return _get_service().start_warm_cache(run_id)


@router.get("/runs/{run_id}/warm-cache")
def warm_run_cache_status(run_id: int) -> Dict[str, Any]:
    """Get status of cache warming job."""
    return _get_service().get_warm_cache_status(run_id)
