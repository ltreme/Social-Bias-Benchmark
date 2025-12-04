#!/usr/bin/env python3
"""Check if dual pairs exist and test the order metrics calculation."""

import pandas as pd

from backend.domain.analytics.benchmarks.metrics import compute_order_effect_metrics
from backend.infrastructure.benchmark import data_loader
from backend.infrastructure.storage.db import get_db, init_database
from backend.infrastructure.storage.models import BenchmarkResult

init_database()

# Test for run 42
run_id = 42
print(f"=== Testing run {run_id} ===")

# Load DataFrame
print("Loading DataFrame...")
df = data_loader.load_run_df(run_id)
print(f"DataFrame shape: {df.shape}")
print(f"Columns: {list(df.columns)}")

if "scale_order" in df.columns:
    print(f"\nscale_order value counts:")
    print(df["scale_order"].value_counts())

    print(f"\nChecking for rating_raw column: {'rating_raw' in df.columns}")

    # Check how many pairs exist
    print("\nChecking for dual pairs...")
    sub = df.loc[
        df["scale_order"].isin(["in", "rev"]),
        ["persona_uuid", "case_id", "rating", "scale_order"],
    ].copy()
    print(f"Filtered subset shape: {sub.shape}")

    piv = sub.pivot_table(
        index=["persona_uuid", "case_id"],
        columns="scale_order",
        values="rating",
        aggfunc="first",
    ).reset_index()

    print(f"Pivot table shape: {piv.shape}")
    print(f"Pivot columns: {list(piv.columns)}")

    if "in" in piv.columns and "rev" in piv.columns:
        pairs = piv.dropna(subset=["in", "rev"])
        print(f"Pairs with both in and rev: {len(pairs)}")
        if len(pairs) > 0:
            print(f"Sample pair:")
            print(pairs.head(1))
    else:
        print("WARNING: Missing 'in' or 'rev' column in pivot!")

# Now test compute_order_effect_metrics
print("\n=== Testing compute_order_effect_metrics ===")
metrics = compute_order_effect_metrics(df)
print(f"n_pairs: {metrics.get('n_pairs')}")
print(f"rma: {metrics.get('rma')}")
print(f"by_case length: {len(metrics.get('by_case', []))}")
print(f"by_trait_category length: {len(metrics.get('by_trait_category', []))}")
