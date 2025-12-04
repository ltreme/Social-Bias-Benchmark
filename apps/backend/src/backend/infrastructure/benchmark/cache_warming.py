"""Cache warming background worker for benchmark analysis."""

from __future__ import annotations

import copy
import logging
import threading
import time
from contextlib import nullcontext
from typing import Any, Callable, Dict, Optional

from backend.infrastructure.storage.db import get_db
from backend.infrastructure.storage.models import utcnow

_WARM_CACHE_JOBS: Dict[int, Dict[str, Any]] = {}
_WARM_CACHE_LOCK = threading.Lock()
_LOG = logging.getLogger(__name__)

_DEFAULT_ANALYSIS_ATTRIBUTES = [
    "gender",
    "origin_subregion",
    "religion",
    "migration_status",
    "sexuality",
    "marriage_status",
    "education",
]


def get_warm_cache_job(run_id: int) -> Optional[Dict[str, Any]]:
    """Get the current warm cache job for a run."""
    return _WARM_CACHE_JOBS.get(run_id)


def clear_warm_cache_job(run_id: int) -> None:
    """Clear the warm cache job for a run, allowing it to be re-run."""
    with _WARM_CACHE_LOCK:
        if run_id in _WARM_CACHE_JOBS:
            del _WARM_CACHE_JOBS[run_id]


def warm_job_snapshot(run_id: int, job: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a snapshot of a warm cache job for API response.

    Args:
        run_id: The benchmark run ID
        job: The job dict, or None

    Returns:
        Snapshot dict suitable for API response
    """
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


def start_warm_cache_job(
    run_id: int,
    metrics_fn: Callable,
    missing_fn: Callable,
    order_metrics_fn: Callable,
    means_fn: Callable,
    deltas_fn: Callable,
    forest_fn: Callable,
) -> Dict[str, Any]:
    """Start an asynchronous warm cache job.

    Args:
        run_id: The benchmark run ID
        metrics_fn: Function to compute metrics
        missing_fn: Function to compute missing data
        order_metrics_fn: Function to compute order metrics
        means_fn: Function to compute means
        deltas_fn: Function to compute deltas
        forest_fn: Function to compute forest plot data

    Returns:
        Job status dict
    """
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
        args=(
            run_id,
            job,
            metrics_fn,
            missing_fn,
            order_metrics_fn,
            means_fn,
            deltas_fn,
            forest_fn,
        ),
        daemon=True,
        name=f"warm-cache-{run_id}",
    )
    thread.start()
    return copy.deepcopy(job)


def _warm_cache_worker(
    run_id: int,
    job: Dict[str, Any],
    metrics_fn: Callable,
    missing_fn: Callable,
    order_metrics_fn: Callable,
    means_fn: Callable,
    deltas_fn: Callable,
    forest_fn: Callable,
) -> None:
    """Background worker that warms the cache.

    Args:
        run_id: The benchmark run ID
        job: The job status dict
        metrics_fn: Function to compute metrics
        missing_fn: Function to compute missing data
        order_metrics_fn: Function to compute order metrics
        means_fn: Function to compute means
        deltas_fn: Function to compute deltas
        forest_fn: Function to compute forest plot data
    """
    started = time.time()
    _LOG.info("[warm-cache:%s] worker started", run_id)
    try:
        try:
            db = get_db()
            ctx = db.connection_context()
        except Exception:
            ctx = nullcontext()
        metrics_payload: Dict[str, Any] = {}
        with ctx:
            metrics_payload = _run_warm_step(job, "metrics", metrics_fn, run_id) or {}
            _run_warm_step(job, "missing", missing_fn, run_id)
            _run_warm_step(job, "order_metrics", order_metrics_fn, run_id)
            for attr in _DEFAULT_ANALYSIS_ATTRIBUTES:
                _run_warm_step(job, f"means:{attr}", means_fn, run_id, attr)
                _run_warm_step(job, f"deltas:{attr}", deltas_fn, run_id, attr)

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
                    deltas_fn,
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
                forest_fn,
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
    """Execute a single cache warming step.

    Args:
        job: The job status dict
        label: Step label
        fn: Function to execute
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result, or None on error
    """
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
