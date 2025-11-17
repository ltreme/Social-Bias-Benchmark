from __future__ import annotations

import argparse
import os
import sys

from backend.domain.benchmarking.adapters.postprocess.postprocessor_likert import (
    LikertPostProcessor,
)
from backend.domain.benchmarking.adapters.prompting import LikertPromptFactory
from backend.domain.benchmarking.benchmark import run_benchmark_pipeline
from backend.infrastructure.benchmark.persister_bench_sqlite import (
    BenchPersisterPeewee,
    BenchPersisterPrint,
)
from backend.infrastructure.llm import (
    LlmClientFakeBench,
    LlmClientHFBench,
    LlmClientVLLMBench,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run primary bias benchmark pipeline.")
    p.add_argument(
        "--gen-id",
        type=int,
        required=False,
        help="DEPRECATED: Use --dataset-id instead. Persona generation run id (ignored when --dataset-id is set)",
    )
    p.add_argument(
        "--dataset-id",
        type=int,
        required=False,
        help="Use personas from a Dataset (DatasetPersona membership)",
    )
    p.add_argument(
        "--attrgen-run-id",
        type=int,
        required=False,
        help="Use additional attributes from this AttrGenerationRun (ensures model-consistent enrichment)",
    )
    # Optional: override the system prompt preamble
    p.add_argument("--system-prompt", type=str, help="Override system prompt/preamble")
    p.add_argument("--max-attempts", type=int, default=2)
    p.add_argument(
        "--llm",
        choices=["fake", "hf", "vllm"],
        default="vllm",
        help="LLM backend: vllm (preferred), hf (deprecated), or fake (testing)",
    )
    p.add_argument(
        "--hf-model",
        type=str,
        help="[DEPRECATED] HF model name/path (only when --llm=hf)",
    )
    # vLLM OpenAI-compatible server options
    p.add_argument(
        "--vllm-base-url",
        type=str,
        default="http://localhost:8000",
        help="Base URL of vLLM server root (e.g., http://host:port)",
    )
    p.add_argument(
        "--vllm-model", type=str, help="Model name served by vLLM (when --llm=vllm)"
    )
    p.add_argument(
        "--vllm-api-key",
        type=str,
        default=None,
        help="Optional API key for vLLM server",
    )
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--persist", choices=["print", "peewee"], default="peewee")
    p.add_argument("--max-new-tokens", type=int, default=256)
    p.add_argument(
        "--trait-file",
        type=str,
        help="Path to Likert trait CSV (headers: id,adjective,...)",
    )
    p.add_argument(
        "--with-rational",
        choices=["on", "off"],
        default="on",
        help="Include short rationale in output JSON (default: on)",
    )
    args = p.parse_args(argv)

    # Init DB (SQLite by default or DB_URL)
    from backend.infrastructure.storage.db import create_tables, init_database

    init_database()
    create_tables()

    # Persona + Question repositories
    from backend.infrastructure.benchmark.repository.persona_repository import (
        FullPersonaRepository,
        FullPersonaRepositoryByDataset,
    )
    from backend.infrastructure.benchmark.repository.trait import TraitRepository

    if args.trait_file:
        if not args.trait_file.endswith(".csv") or not os.path.isfile(args.trait_file):
            print("[fatal] --trait-file must be a CSV file", file=sys.stderr)
            return 2
        trait_repo = TraitRepository(path=args.trait_file)
    else:
        trait_repo = TraitRepository()

    include_rationale = args.with_rational == "on"

    prompt_factory = LikertPromptFactory(
        max_new_tokens=args.max_new_tokens,
        system_preamble=args.system_prompt,
        include_rationale=include_rationale,
    )
    post = LikertPostProcessor(include_rationale=include_rationale)

    if args.llm == "fake":
        llm = LlmClientFakeBench(batch_size=args.batch_size)
        model_name = "fake"
    elif args.llm == "hf":
        print("[warn] --llm=hf is deprecated. Prefer --llm=vllm.", file=sys.stderr)
        if not args.hf_model:
            print("[fatal] --hf-model is required when --llm=hf", file=sys.stderr)
            return 2
        llm = LlmClientHFBench(
            model_name_or_path=args.hf_model, batch_size=args.batch_size
        )
        model_name = args.hf_model
    else:  # vllm
        if not args.vllm_model:
            print("[fatal] --vllm-model is required when --llm=vllm", file=sys.stderr)
            return 2
        llm = LlmClientVLLMBench(
            base_url=args.vllm_base_url,
            model=args.vllm_model,
            api_key=args.vllm_api_key,
            batch_size=args.batch_size,
            max_new_tokens_cap=args.max_new_tokens,
        )
        model_name = args.vllm_model

    # Instantiate persona repo after model_name is known; restrict by attrgen run if provided
    persona_repo = FullPersonaRepository(
        model_name=model_name, attr_generation_run_id=args.attrgen_run_id
    )
    persona_count_override = None
    if args.dataset_id is not None:
        # Switch to dataset-backed repo
        persona_repo = FullPersonaRepositoryByDataset(
            dataset_id=int(args.dataset_id),
            model_name=model_name,
            attr_generation_run_id=args.attrgen_run_id,
        )
        # Validate that attrgen-run belongs to this dataset if provided
        if args.attrgen_run_id is not None:
            try:
                from backend.infrastructure.storage.models import AttrGenerationRun

                r = AttrGenerationRun.get_by_id(int(args.attrgen_run_id))
                if int(r.dataset_id.id) != int(args.dataset_id):
                    print(
                        "[fatal] --attrgen-run-id gehört zu einem anderen Dataset",
                        file=sys.stderr,
                    )
                    return 2
                # Optional: warn if model mismatch
                if getattr(r.model_id, "name", None) and str(r.model_id.name) != str(
                    model_name
                ):
                    print(
                        f"[warn] attrgen model ({r.model_id.name}) != benchmark model ({model_name})",
                        file=sys.stderr,
                    )
            except Exception as e:
                print(
                    f"[fatal] could not validate --attrgen-run-id: {e}", file=sys.stderr
                )
                return 2
        try:
            from backend.infrastructure.storage.models import DatasetPersona

            persona_count_override = (
                DatasetPersona.select()
                .where(DatasetPersona.dataset_id == int(args.dataset_id))
                .count()
            )
        except Exception as e:
            print(f"[warn] could not count personas in dataset: {e}", file=sys.stderr)

    persist = (
        BenchPersisterPrint() if args.persist == "print" else BenchPersisterPeewee()
    )

    # Create a BenchmarkRun record to capture parameters for traceability
    from backend.infrastructure.storage import models as dbm

    try:
        # Get or create model entry
        model_entry = dbm.Model.get_or_create(name=model_name)[0]
        bench_run = dbm.BenchmarkRun.create(
            dataset_id=args.dataset_id,
            model_id=model_entry.id,
            batch_size=args.batch_size,
            max_attempts=args.max_attempts,
            include_rationale=include_rationale,
            system_prompt=args.system_prompt,
        )
        benchmark_run_id = bench_run.id
    except Exception as e:
        print(f"[warn] failed to record BenchmarkRun: {e}", file=sys.stderr)
        benchmark_run_id = None  # still run pipeline

    run_benchmark_pipeline(
        dataset_id=args.dataset_id,
        trait_repo=trait_repo,
        persona_repo=persona_repo,
        prompt_factory=prompt_factory,
        llm=llm,
        post=post,
        persist=persist,
        model_name=model_name,
        benchmark_run_id=benchmark_run_id,
        max_attempts=args.max_attempts,
        persona_count_override=persona_count_override,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
