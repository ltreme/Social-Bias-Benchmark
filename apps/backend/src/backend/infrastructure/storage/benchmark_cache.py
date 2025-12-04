"""Persistent cache for benchmark metrics and analysis results."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from backend.infrastructure.storage.models import BenchCache, BenchmarkResult, utcnow


def result_row_count(run_id: int) -> int:
    """Count the number of result rows for a benchmark run.

    Args:
        run_id: The benchmark run ID

    Returns:
        Number of result rows
    """
    try:
        return int(
            BenchmarkResult.select()
            .where(BenchmarkResult.benchmark_run_id == run_id)
            .count()
        )
    except Exception:
        return 0


def cache_key(run_id: int, kind: str, params: Dict[str, Any]) -> str:
    """Generate a cache key for a benchmark query.

    The key includes the result row count to invalidate cache when data changes.

    Args:
        run_id: The benchmark run ID
        kind: The type of cached data (e.g., 'metrics', 'deltas')
        params: Additional parameters that affect the result

    Returns:
        JSON-encoded cache key
    """
    key = {"r": result_row_count(run_id), **params}
    try:
        return json.dumps(key, sort_keys=True, ensure_ascii=False)
    except Exception:
        return json.dumps(
            {"r": key.get("r"), "params": str(params)},
            sort_keys=True,
            ensure_ascii=False,
        )


def get_cached(run_id: int, kind: str, key: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached data from the database.

    Args:
        run_id: The benchmark run ID
        kind: The type of cached data
        key: The cache key

    Returns:
        Cached data as dict, or None if not found
    """
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


def put_cached(run_id: int, kind: str, key: str, payload: Dict[str, Any]) -> None:
    """Store data in the cache.

    Args:
        run_id: The benchmark run ID
        kind: The type of cached data
        key: The cache key
        payload: The data to cache
    """
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
