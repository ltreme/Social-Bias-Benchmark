"""Progress tracking for running benchmarks."""

from __future__ import annotations

import threading
import time
from typing import Any, Dict

from backend.infrastructure.benchmark.repository.trait import TraitRepository
from backend.infrastructure.storage.models import (
    BenchmarkResult,
    BenchmarkRun,
    DatasetPersona,
)

# Global state for tracking benchmark progress
_BENCH_PROGRESS: dict[int, dict] = {}


def get_progress(run_id: int) -> Dict[str, Any]:
    """Get current progress for a benchmark run."""
    return _BENCH_PROGRESS.get(run_id, {})


def set_progress(run_id: int, progress: Dict[str, Any]) -> None:
    """Set progress for a benchmark run."""
    _BENCH_PROGRESS.setdefault(run_id, {})
    _BENCH_PROGRESS[run_id].update(progress)


def clear_progress(run_id: int) -> None:
    """Clear progress for a benchmark run."""
    _BENCH_PROGRESS.pop(run_id, None)


def _progress_status(info: Dict[str, Any]) -> str:
    """Determine status based on progress info."""
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


def update_progress(run_id: int, dataset_id: int) -> None:
    """Update progress information for a benchmark run.

    Args:
        run_id: The benchmark run ID
        dataset_id: The dataset ID being benchmarked
    """
    # Get existing info to check if we need to update count
    existing_info = _BENCH_PROGRESS.get(run_id, {})
    now = time.time()
    last_count_update = existing_info.get("_last_count_update", 0)

    # Only update count every 30 seconds to avoid expensive DB queries
    # (COUNT DISTINCT on large tables is slow, especially on PostgreSQL)
    needs_count_update = (now - last_count_update) > 30.0

    if needs_count_update:
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
    else:
        # Use cached count
        done = existing_info.get("done", 0)

    # Get expected total from the run's progress info if available (for running benchmarks)
    # Otherwise calculate based on current active traits
    existing_info = _BENCH_PROGRESS.get(run_id, {})

    # Only recalculate total if the benchmark is actively running
    # For completed/partial runs, keep the original total or use done count
    if existing_info.get("status") in {"queued", "running", "cancelling"}:
        # Cache total calculation too - it's expensive and rarely changes
        last_total_update = existing_info.get("_last_total_update", 0)
        needs_total_update = (now - last_total_update) > 60.0  # Update every minute

        if needs_total_update:
            try:
                traits = TraitRepository().count()
            except Exception:
                traits = 0
            total_personas = (
                DatasetPersona.select()
                .where(DatasetPersona.dataset_id == dataset_id)
                .count()
            )
            base_total = total_personas * traits if traits and total_personas else 0
            # Estimate duplicates by dual_fraction
            try:
                br = BenchmarkRun.get_by_id(run_id)
                frac = float(getattr(br, "dual_fraction", 0.0) or 0.0)
            except Exception:
                frac = float(existing_info.get("dual_fraction") or 0.0)
            extra = int(round(base_total * frac)) if base_total and frac else 0
            total = base_total + extra
            if done > total:
                total = done
            # Cache the total
            existing_info["_cached_total"] = total
            existing_info["_last_total_update"] = now
        else:
            # Use cached total
            total = existing_info.get("_cached_total", done)
            if done > total:
                total = done
    else:
        # For non-running benchmarks, use done count as total (it's complete)
        total = existing_info.get("total", done)
        # If we have more results than expected, update total
        if done > total:
            total = done

    pct = (100.0 * done / total) if total else 0.0
    _BENCH_PROGRESS.setdefault(run_id, {})
    entry = _BENCH_PROGRESS[run_id]
    entry.update({"done": done, "total": total, "pct": pct})
    if needs_count_update:
        entry["_last_count_update"] = now  # Track when we last counted
    if entry.get("status") in (None, "unknown"):
        entry["status"] = _progress_status(entry)


def progress_poller(run_id: int, dataset_id: int) -> None:
    """Background poller that updates progress periodically.

    Args:
        run_id: The benchmark run ID
        dataset_id: The dataset ID being benchmarked
    """
    try:
        while _BENCH_PROGRESS.get(run_id, {}).get("status") in {
            "queued",
            "running",
            "cancelling",
        }:
            if _BENCH_PROGRESS.get(run_id, {}).get("cancel_requested"):
                _BENCH_PROGRESS[run_id]["status"] = "cancelling"
            update_progress(run_id, dataset_id)
            time.sleep(2.0)
    except Exception:
        pass


def get_completed_keys(run_id: int) -> set[tuple[str, str, str]]:
    """Get all completed (persona, case, order) keys for a run.

    Args:
        run_id: The benchmark run ID

    Returns:
        Set of tuples (persona_uuid, case_id, scale_order)
    """
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
