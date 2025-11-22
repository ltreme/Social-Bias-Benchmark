"""Data loading utilities for benchmark results."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from backend.domain.analytics.benchmarks.analytics import (
    BenchQuery,
    load_benchmark_dataframe,
)


def load_run_df(run_id: int) -> pd.DataFrame:
    """Load benchmark results as a DataFrame.

    Args:
        run_id: The benchmark run ID

    Returns:
        DataFrame with benchmark results joined with persona and trait data
    """
    cfg = BenchQuery(run_ids=(run_id,))
    df = load_benchmark_dataframe(cfg)
    return df


@lru_cache(maxsize=64)
def load_run_df_cached(run_id: int) -> pd.DataFrame:
    """Load benchmark results with caching.

    Cache the joined dataframe for expensive endpoints.

    Args:
        run_id: The benchmark run ID

    Returns:
        Cached DataFrame with benchmark results
    """
    return load_run_df(run_id)


def df_for_read(run_id: int, progress_getter=None) -> pd.DataFrame:
    """Return appropriate DataFrame for a run based on its status.

    Returns cached DF for finished runs; live DF while running.

    Args:
        run_id: The benchmark run ID
        progress_getter: Optional function to get progress info

    Returns:
        DataFrame with benchmark results
    """
    if progress_getter:
        info = progress_getter(run_id)
        if info.get("status") in {"running", "queued"}:
            return load_run_df(run_id)
    return load_run_df_cached(run_id)


def clear_cache() -> None:
    """Clear the DataFrame cache."""
    try:
        load_run_df_cached.cache_clear()
    except Exception:
        pass
