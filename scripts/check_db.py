#!/usr/bin/env python3
"""Check database for debugging Order-Consistency issues."""

from peewee import fn

from backend.infrastructure.storage.db import get_db, init_database
from backend.infrastructure.storage.models import BenchmarkResult, BenchmarkRun, Trait

init_database()
db = get_db()

# Check traits
print("=== Traits (first 5) ===")
for t in Trait.select().limit(5):
    print(f"  id={t.id!r}, adj={t.adjective!r}, cat={t.category!r}")

print()

# Check scale_order values
print("=== scale_order values ===")
orders = BenchmarkResult.select(
    BenchmarkResult.scale_order, fn.COUNT(BenchmarkResult.id).alias("cnt")
).group_by(BenchmarkResult.scale_order)
for o in orders:
    print(f"  scale_order={o.scale_order!r}: count={o.cnt}")

# Check dual pairs
print()
print("=== Dual pairs check ===")
in_count = BenchmarkResult.select().where(BenchmarkResult.scale_order == "in").count()
rev_count = BenchmarkResult.select().where(BenchmarkResult.scale_order == "rev").count()
print(f"in: {in_count}, rev: {rev_count}")

# Check runs
print()
print("=== Runs ===")
for run in BenchmarkRun.select().limit(5):
    result_count = (
        BenchmarkResult.select()
        .where(BenchmarkResult.benchmark_run_id == run.id)
        .count()
    )
    in_count = (
        BenchmarkResult.select()
        .where(
            (BenchmarkResult.benchmark_run_id == run.id)
            & (BenchmarkResult.scale_order == "in")
        )
        .count()
    )
    rev_count = (
        BenchmarkResult.select()
        .where(
            (BenchmarkResult.benchmark_run_id == run.id)
            & (BenchmarkResult.scale_order == "rev")
        )
        .count()
    )
    print(f"  Run {run.id}: total={result_count}, in={in_count}, rev={rev_count}")

# Check case_ids
print()
print("=== Case IDs match Trait IDs ===")
trait_ids = set(t.id for t in Trait.select())
result_case_ids = set()
for r in BenchmarkResult.select(BenchmarkResult.case_id).distinct():
    case_id = r.case_id
    if hasattr(case_id, "id"):
        result_case_ids.add(case_id.id)
    else:
        result_case_ids.add(str(case_id))

print(f"Trait IDs count: {len(trait_ids)}")
print(f"Result case_ids count: {len(result_case_ids)}")
print(f"Sample trait IDs: {list(trait_ids)[:5]}")
print(f"Sample result case_ids: {list(result_case_ids)[:5]}")
matched = trait_ids & result_case_ids
print(f"Matched: {len(matched)}")
