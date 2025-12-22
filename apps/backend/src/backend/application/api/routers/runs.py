"""Benchmark runs API router - simplified to pure routing logic."""

from __future__ import annotations

import csv
import io
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
from backend.infrastructure.storage import benchmark_cache

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


@router.get("/runs/{run_id}/kruskal-by-category")
def run_kruskal_wallis_by_trait_category(run_id: int) -> Dict[str, Any]:
    """Get Kruskal-Wallis test results per trait category.

    Tests whether response distributions differ significantly across groups
    within each demographic attribute, separately for each trait category
    (e.g., Kompetenz, Wärme, Moral).
    """
    return _get_analytics_service().get_kruskal_wallis_by_trait_category(run_id)


@router.post("/runs/{run_id}/warm-cache")
def warm_run_cache(run_id: int) -> Dict[str, Any]:
    """Start asynchronous cache warming job for a run."""
    return _get_analytics_service().start_warm_cache(run_id)


@router.get("/runs/{run_id}/warm-cache")
def warm_run_cache_status(run_id: int) -> Dict[str, Any]:
    """Get status of cache warming job."""
    return _get_analytics_service().get_warm_cache_status(run_id)


@router.delete("/runs/{run_id}/cache")
def clear_run_cache(run_id: int) -> Dict[str, Any]:
    """Clear all cached analytics data for a run.

    This removes computed metrics, deltas, forests etc. from the cache,
    forcing them to be recomputed on next request.
    """
    deleted = benchmark_cache.clear_run_cache(run_id)
    return {"ok": True, "deleted": deleted}


# ============================================================================
# Analysis Endpoints (Queue-based)
# ============================================================================


def _get_analysis_service():
    """Get analysis service instance."""
    from backend.application.services.analysis_service import get_analysis_service

    ensure_db()
    return get_analysis_service()


def _get_export_service():
    """Get export service instance."""
    from backend.application.services.benchmark_export_service import (
        BenchmarkExportService,
    )

    ensure_db()
    return BenchmarkExportService()


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

    Note: Order analysis is no longer queued - it's computed synchronously.
    """
    analysis_type = body.get("type")
    if not analysis_type:
        raise HTTPException(status_code=400, detail="Missing 'type' in request body")

    if analysis_type not in ("order", "bias", "export"):
        raise HTTPException(
            status_code=400, detail=f"Invalid analysis type: {analysis_type}"
        )

    # Order analysis is now synchronous via get_order_metrics
    if analysis_type == "order":
        return {
            "job_id": None,
            "task_id": None,
            "status": "completed",
            "message": "Order metrics are computed synchronously. Use /runs/{run_id}/order-metrics endpoint.",
        }

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


@router.get("/runs/{run_id}/export/json")
def export_run_data(run_id: int) -> StreamingResponse:
    """Export all run data as JSON for LLM analysis."""
    export_service = _get_export_service()
    report = export_service.get_export_data(run_id)

    if not report:
        raise HTTPException(status_code=404, detail="Run not found or export failed")

    return StreamingResponse(
        iter([json.dumps(report, indent=2, ensure_ascii=False)]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=run_{run_id}_data.json"},
    )


# ============================================================================
# Multi-Run Comparison Endpoints
# ============================================================================


@router.post("/runs/compare/metrics")
def compare_runs_metrics(body: dict) -> Dict[str, Any]:
    """Get aggregated metrics across multiple runs.

    Body: {
        run_ids: List[int]
    }

    Returns combined rating distribution and basic stats.
    """
    run_ids = body.get("run_ids", [])
    if not run_ids:
        raise HTTPException(status_code=400, detail="Missing 'run_ids' in request body")

    try:
        return _get_analytics_service().get_multi_run_metrics(run_ids)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error computing multi-run metrics: {str(e)}"
        )


@router.post("/runs/compare/order-metrics")
def compare_runs_order_metrics(body: dict) -> Dict[str, Any]:
    """Get aggregated order consistency metrics across multiple runs.

    Body: {
        run_ids: List[int]
    }

    Returns aggregated RMA, Cliff's Delta, MAE, correlation, etc.
    """
    run_ids = body.get("run_ids", [])
    if not run_ids:
        raise HTTPException(status_code=400, detail="Missing 'run_ids' in request body")

    try:
        return _get_analytics_service().get_multi_run_order_metrics(run_ids)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error computing multi-run order metrics: {str(e)}"
        )


@router.post("/runs/compare/deltas")
def compare_runs_deltas(body: dict) -> Dict[str, Any]:
    """Get aggregated bias deltas across multiple runs.

    Body: {
        run_ids: List[int],
        trait_category?: str  # Optional filter
    }

    Returns bias intensity scores aggregated for all standard attributes.
    """
    run_ids = body.get("run_ids", [])
    if not run_ids:
        raise HTTPException(status_code=400, detail="Missing 'run_ids' in request body")

    trait_category = body.get("trait_category")
    try:
        return _get_analytics_service().get_multi_run_deltas(
            run_ids, trait_category=trait_category
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error computing multi-run deltas: {str(e)}"
        )


@router.post("/runs/compare/bias-intensity-csv")
def export_bias_intensity_csv(body: dict) -> StreamingResponse:
    """Export bias intensity comparison table as CSV.

    Body: {
        run_ids: List[int],
        trait_category?: str  # Optional: 'all', 'kompetenz', 'sozial'
    }

    Returns CSV with format:
    Merkmal,Run #1,Run #2,...
    Herkunft,21.0,21.7,...
    ...
    Average,23.6,23.1,...
    """
    run_ids = body.get("run_ids", [])
    if not run_ids:
        raise HTTPException(status_code=400, detail="Missing 'run_ids' in request body")

    trait_category = body.get("trait_category")

    try:
        analytics_service = _get_analytics_service()

        # Attribute labels in German
        attr_labels = {
            "gender": "Geschlecht",
            "age_group": "Altersgruppe",
            "religion": "Religion",
            "sexuality": "Sexualität",
            "marriage_status": "Familienstand",
            "education": "Bildung",
            "origin_subregion": "Herkunft",
            "migration_status": "Migration",
        }

        # Standard attribute order
        attributes = [
            "origin_subregion",
            "age_group",
            "gender",
            "education",
            "marriage_status",
            "sexuality",
            "religion",
            "migration_status",
        ]

        # Get bias intensity for each run
        run_data = []
        for run_id in run_ids:
            deltas = analytics_service.get_all_deltas(
                run_id, trait_category=trait_category
            )
            if deltas.get("ok"):
                run_info = analytics_service._get_run_info(run_id)
                run_data.append(
                    {
                        "run_id": run_id,
                        "model": run_info.get("model_name", f"Run {run_id}"),
                        "deltas": deltas.get("data", {}),
                    }
                )

        # Build CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        header = ["Merkmal"] + [f"Run #{r['run_id']}" for r in run_data]
        writer.writerow(header)

        # Data rows - one per attribute
        totals = [0.0] * len(run_data)
        valid_counts = [0] * len(run_data)

        for attr in attributes:
            row = [attr_labels.get(attr, attr)]
            for idx, run in enumerate(run_data):
                attr_data = run["deltas"].get(attr, {})
                if attr_data.get("ok") and "rows" in attr_data:
                    rows = attr_data["rows"]
                    cliffs_deltas = [
                        abs(r.get("cliffs_delta"))
                        for r in rows
                        if r.get("cliffs_delta") is not None
                    ]
                    if cliffs_deltas:
                        max_cliffs = max(cliffs_deltas)
                        avg_cliffs = sum(cliffs_deltas) / len(cliffs_deltas)
                        # Apply same formula as frontend
                        scaled_max = min(max_cliffs * 4.0, 1.0)
                        scaled_avg = min(avg_cliffs * 4.0, 1.0)
                        bias_intensity = (0.6 * scaled_max + 0.4 * scaled_avg) * 100
                        row.append(f"{bias_intensity:.1f}")
                        totals[idx] += bias_intensity
                        valid_counts[idx] += 1
                    else:
                        row.append("0.0")
                else:
                    row.append("–")
            writer.writerow(row)

        # Average row
        avg_row = ["Average"]
        for idx in range(len(run_data)):
            if valid_counts[idx] > 0:
                avg = totals[idx] / valid_counts[idx]
                avg_row.append(f"{avg:.1f}")
            else:
                avg_row.append("–")
        writer.writerow(avg_row)

        # Prepare response
        output.seek(0)
        category_suffix = f"_{trait_category}" if trait_category else "_all"
        filename = f"bias_intensity_comparison{category_suffix}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating CSV: {str(e)}")
