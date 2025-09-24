import argparse
import json
from typing import Optional

from shared.storage.db import init_database, create_tables
from shared.storage.models import Dataset, DatasetPersona, CounterfactualLink
from shared.datasets.builder import (
    build_balanced_dataset_from_pool,
    build_counterfactuals_from_dataset,
    build_random_subset_from_pool,
)

# Reuse persona generator internals
from persona_generator.main import sample_personas, persist_run_and_personas


def cmd_generate_pool(args: argparse.Namespace) -> None:
    init_database()
    create_tables()

    params = dict(
        age_min=args.age_from,
        age_max=args.age_to,
        age_temperature=args.temperature,
        education_temperature=args.temperature,
        education_exclude=None,
        gender_temperature=args.temperature,
        gender_exclude=None,
        occupation_exclude=None,
        marriage_status_temperature=args.temperature,
        marriage_status_exclude=None,
        migration_status_temperature=args.temperature,
        migration_status_exclude=None,
        origin_temperature=args.temperature,
        origin_exclude=None,
        religion_temperature=args.temperature,
        religion_exclude=None,
        sexuality_temperature=args.temperature,
        sexuality_exclude=None,
    )

    sampled = sample_personas(n=args.n, **params)
    dataset_id = persist_run_and_personas(n=args.n, params=params, sampled=sampled, export_csv_path=None)

    # Register dataset
    ds_name = args.name or f"pool-{dataset_id}-n{args.n}"
    ds = Dataset.create(
        name=ds_name,
        kind="pool",
        config_json=json.dumps({"n": args.n, "temperature": args.temperature, "age_range": [args.age_from, args.age_to]}, ensure_ascii=False),
    )
    print(f"OK: generated pool and registered dataset '{ds.name}' (id={ds.id})")


def cmd_build_balanced(args: argparse.Namespace) -> None:
    init_database()
    create_tables()
    ds = build_balanced_dataset_from_pool(dataset_id=args.dataset_id, axes=["gender", "age", "origin"], n_target=args.n, seed=args.seed, name=args.name)
    print(f"OK: balanced dataset '{ds.name}' (id={ds.id}) with {DatasetPersona.select().where(DatasetPersona.dataset_id == ds.id).count()} members")


def cmd_build_counterfactuals(args: argparse.Namespace) -> None:
    init_database()
    create_tables()
    ds = build_counterfactuals_from_dataset(dataset_id=args.dataset_id, seed=args.seed, name=args.name)
    print(f"OK: counterfactual dataset '{ds.name}' (id={ds.id}); links={CounterfactualLink.select().where(CounterfactualLink.dataset_id == ds.id).count()} members={DatasetPersona.select().where(DatasetPersona.dataset_id == ds.id).count()}")


def cmd_sample_reality(args: argparse.Namespace) -> None:
    init_database()
    create_tables()
    ds = build_random_subset_from_pool(dataset_id=args.dataset_id, n=args.n, seed=args.seed, name=args.name)
    print(f"OK: reality dataset '{ds.name}' (id={ds.id}) with {DatasetPersona.select().where(DatasetPersona.dataset_id == ds.id).count()} members")


def main():
    parser = argparse.ArgumentParser(description="Dataset builder CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pool = sub.add_parser("generate-pool", help="Generate a large persona pool and register as dataset")
    p_pool.add_argument("--n", type=int, default=20000)
    p_pool.add_argument("--temperature", type=float, default=0.1)
    p_pool.add_argument("--age_from", type=int, default=0)
    p_pool.add_argument("--age_to", type=int, default=100)
    p_pool.add_argument("--name", type=str, default=None)
    p_pool.set_defaults(func=cmd_generate_pool)

    p_bal = sub.add_parser("build-balanced", help="Build balanced dataset from a dataset")
    p_bal.add_argument("--dataset_id", type=int, required=True)
    p_bal.add_argument("--n", type=int, default=2000)
    p_bal.add_argument("--seed", type=int, default=42)
    p_bal.add_argument("--name", type=str, default=None)
    p_bal.set_defaults(func=cmd_build_balanced)

    p_cf = sub.add_parser("build-counterfactuals", help="Build counterfactuals from a dataset (balanced)")
    p_cf.add_argument("--dataset_id", type=int, required=True)
    p_cf.add_argument("--seed", type=int, default=42)
    p_cf.add_argument("--name", type=str, default=None)
    p_cf.set_defaults(func=cmd_build_counterfactuals)

    p_real = sub.add_parser("sample-reality", help="Sample random subset from a dataset")
    p_real.add_argument("--dataset_id", type=int, required=True)
    p_real.add_argument("--n", type=int, default=500)
    p_real.add_argument("--seed", type=int, default=42)
    p_real.add_argument("--name", type=str, default=None)
    p_real.set_defaults(func=cmd_sample_reality)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

