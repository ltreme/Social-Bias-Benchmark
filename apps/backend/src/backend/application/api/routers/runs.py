"""Benchmark runs API router - simplified to pure routing logic."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.application.services.benchmark_analytics_service import (
    BenchmarkAnalyticsService,
)
from backend.application.services.benchmark_run_service import BenchmarkRunService

from ..deps import db_session
from ..utils import ensure_db

router = APIRouter(tags=["runs"], dependencies=[Depends(db_session)])


def _get_run_service() -> BenchmarkRunService:
    """Get benchmark run service instance."""
    ensure_db()
    return BenchmarkRunService()


def _get_analytics_service() -> BenchmarkAnalyticsService:
    """Get benchmark analytics service instance."""
    ensure_db()
    return BenchmarkAnalyticsService()


@router.get("/runs")
def list_runs() -> List[Dict[str, Any]]:
    """List all benchmark runs."""
    return _get_run_service().list_runs()


@router.get("/runs/{run_id}")
def get_run(run_id: int) -> Dict[str, Any]:
    """Get details of a specific benchmark run."""
    return _get_run_service().get_run(run_id)


@router.get("/models")
def list_models() -> List[str]:
    """List all available models."""
    return _get_run_service().list_models()


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
        return _get_run_service().start_benchmark(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/benchmarks/{run_id}/status")
def bench_status(run_id: int) -> dict:
    """Get status of a benchmark run."""
    return _get_run_service().get_status(run_id)


@router.post("/benchmarks/{run_id}/cancel")
def bench_cancel(run_id: int) -> dict:
    """Cancel a running benchmark."""
    result = _get_run_service().cancel_benchmark(run_id)
    if not result.get("ok"):
        raise HTTPException(
            status_code=400, detail=result.get("error", "Unknown error")
        )
    return result


@router.get("/datasets/{dataset_id}/benchmarks/active")
def active_benchmark(dataset_id: int) -> dict:
    """Get active benchmark for a dataset."""
    return _get_run_service().get_active_benchmark(dataset_id)


@router.get("/runs/{run_id}/metrics")
def run_metrics(run_id: int) -> Dict[str, Any]:
    """Get comprehensive metrics for a benchmark run."""
    return _get_analytics_service().get_metrics(run_id)


@router.get("/runs/{run_id}/order-metrics")
def run_order_metrics(run_id: int) -> Dict[str, Any]:
    """Get order effect metrics (in vs. rev)."""
    return _get_analytics_service().get_order_metrics(run_id)


@router.get("/runs/{run_id}/missing")
def run_missing(run_id: int) -> Dict[str, Any]:
    """Get count and sample of missing benchmark results."""
    return _get_run_service().get_missing(run_id)


@router.delete("/runs/{run_id}")
def delete_run(run_id: int) -> Dict[str, Any]:
    """Delete a benchmark run and all associated results."""
    return _get_run_service().delete_run(run_id)


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
    return _get_analytics_service().get_deltas(
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
    return _get_analytics_service().get_means(run_id, attribute, top_n, trait_category)


@router.get("/runs/{run_id}/means/all")
def run_means_all(run_id: int) -> Dict[str, Any]:
    """Get mean ratings for all standard attributes."""
    return _get_analytics_service().get_all_means(run_id)


@router.get("/runs/{run_id}/deltas/all/{trait_category}")
def run_deltas_all(
    run_id: int,
    trait_category: str,
) -> Dict[str, Any]:
    """Get delta analysis for all standard attributes.

    Args:
        run_id: The benchmark run ID
        trait_category: Filter by trait category (e.g. 'kompetenz', 'sozial') or 'all' for no filter
    """
    # Convert 'all' to None for the service
    category_filter = None if trait_category == "all" else trait_category
    return _get_analytics_service().get_all_deltas(
        run_id, trait_category=category_filter
    )


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
    return _get_analytics_service().get_forest(
        run_id, attribute, baseline, target, min_n, trait_category
    )


@router.get("/runs/{run_id}/kruskal")
def run_kruskal_wallis(run_id: int) -> Dict[str, Any]:
    """Get Kruskal-Wallis omnibus test results for all demographic attributes.

    Tests whether response distributions differ significantly across groups
    within each demographic attribute.
    """
    return _get_analytics_service().get_kruskal_wallis(run_id)


@router.post("/runs/{run_id}/warm-cache")
def warm_run_cache(run_id: int) -> Dict[str, Any]:
    """Start asynchronous cache warming job for a run."""
    return _get_analytics_service().start_warm_cache(run_id)


@router.get("/runs/{run_id}/warm-cache")
def warm_run_cache_status(run_id: int) -> Dict[str, Any]:
    """Get status of cache warming job."""
    return _get_analytics_service().get_warm_cache_status(run_id)


# ============================================================================
# Analysis Endpoints (Queue-based)
# ============================================================================


def _get_analysis_service():
    """Get analysis service instance."""
    from backend.application.services.analysis_service import get_analysis_service

    ensure_db()
    return get_analysis_service()


@router.get("/runs/{run_id}/analysis")
def get_analysis_status(run_id: int) -> Dict[str, Any]:
    """Get status of all analyses for a run.

    Returns:
        Dict with status of each analysis type (quick, order, bias:*, export)
    """
    return _get_analysis_service().get_analysis_status(run_id)


@router.get("/runs/{run_id}/analysis/quick")
def get_quick_analysis(run_id: int) -> Dict[str, Any]:
    """Get quick analysis summary for a run.

    Quick analysis is automatically run after benchmark completion.
    Returns the cached result if available.
    """
    summary = _get_analysis_service().get_quick_summary(run_id)
    if summary is None:
        # Not yet computed - run it now (should be fast)
        summary = _get_analysis_service().run_quick_analysis(run_id)
    return summary


@router.post("/runs/{run_id}/analyze")
def request_analysis(run_id: int, body: dict) -> Dict[str, Any]:
    """Request a deep analysis to be queued.

    Body: {
        type: 'order' | 'bias' | 'export',
        attribute?: str (required for bias),
        format?: str (for export, default 'csv')
    }

    Returns:
        Dict with job_id, task_id, status, message
    """
    analysis_type = body.get("type")
    if not analysis_type:
        raise HTTPException(status_code=400, detail="Missing 'type' in request body")

    if analysis_type not in ("order", "bias", "export"):
        raise HTTPException(
            status_code=400, detail=f"Invalid analysis type: {analysis_type}"
        )

    params = {}
    if analysis_type == "bias":
        attribute = body.get("attribute")
        if not attribute:
            raise HTTPException(
                status_code=400, detail="Bias analysis requires 'attribute'"
            )
        params["attribute"] = attribute
    elif analysis_type == "export":
        params["format"] = body.get("format", "csv")

    force = body.get("force", False)

    try:
        return _get_analysis_service().request_deep_analysis(
            run_id=run_id, analysis_type=analysis_type, params=params, force=force
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}/logs")
def download_run_logs(run_id: int) -> StreamingResponse:
    """Download prompt/response logs for a benchmark run as JSON.

    Filters the JSONL log files to only include entries for this run.
    Returns a JSON array of log entries.
    """
    log_dir = Path(os.environ.get("PROMPT_LOG_DIR", "/app/logs"))

    def generate():
        yield "["
        first = True

        # Find all prompt log files (including rotated ones)
        log_files = sorted(log_dir.glob("prompts.jsonl*"), reverse=True)

        for log_file in log_files:
            if not log_file.exists():
                continue
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if entry.get("run_id") == run_id:
                                if not first:
                                    yield ","
                                yield json.dumps(entry, ensure_ascii=False)
                                first = False
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

        yield "]"

    return StreamingResponse(
        generate(),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=run_{run_id}_logs.json"},
    )
