#!/usr/bin/env python3
"""Test the full get_order_metrics from the service."""

from backend.application.services.benchmark_analytics_service import (
    BenchmarkAnalyticsService,
)
from backend.infrastructure.storage.db import get_db, init_database

init_database()

# Test for run 42
run_id = 42
print(f"=== Testing get_order_metrics for run {run_id} ===")

service = BenchmarkAnalyticsService()

from backend.infrastructure.benchmark import data_loader

# Clear any cached data first
from backend.infrastructure.storage import benchmark_cache

print("Clearing caches...")
benchmark_cache.clear_run_cache(run_id)
data_loader.clear_cache()

print("Calling get_order_metrics...")
try:
    metrics = service.get_order_metrics(run_id)
    print(f"ok: {metrics.get('ok')}")
    print(f"n_pairs: {metrics.get('n_pairs')}")
    print(f"rma: {metrics.get('rma')}")
    print(f"by_case length: {len(metrics.get('by_case', []))}")
    print(f"by_trait_category length: {len(metrics.get('by_trait_category', []))}")

    if metrics.get("by_case"):
        print(f"\nSample by_case entry:")
        print(metrics["by_case"][0])

    if metrics.get("by_trait_category"):
        print(f"\nby_trait_category:")
        for tc in metrics["by_trait_category"]:
            print(f"  {tc}")
except Exception as e:
    import traceback

    print(f"Error: {e}")
    traceback.print_exc()
