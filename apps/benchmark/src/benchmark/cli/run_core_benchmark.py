from __future__ import annotations
import argparse, sys

from benchmark.pipeline.benchmark import run_benchmark_pipeline
from benchmark.pipeline.adapters.prompting import LikertPromptFactory
from benchmark.pipeline.adapters.postprocess.postprocessor_likert import LikertPostProcessor
from benchmark.pipeline.adapters.persister_bench_sqlite import BenchPersisterPrint, BenchPersisterPeewee
from benchmark.pipeline.adapters.llm import LlmClientFakeBench, LlmClientHFBench
import os


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run primary bias benchmark pipeline.")
    p.add_argument("--gen-id", type=int, required=True)
    # Optional: override the system prompt preamble
    p.add_argument("--system-prompt", type=str, help="Override system prompt/preamble")
    p.add_argument("--max-attempts", type=int, default=2)
    p.add_argument("--llm", choices=["fake", "hf"], default="hf")
    p.add_argument("--hf-model", type=str, help="HF model name/path (when --llm=hf)")
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--persist", choices=["print", "peewee"], default="peewee")
    p.add_argument("--max-new-tokens", type=int, default=256)
    p.add_argument("--question-file", type=str, help="Path to question file (csv)")
    p.add_argument("--with-rational", choices=["on", "off"], default="on",
                help="Include short rationale in output JSON (default: on)")
    args = p.parse_args(argv)

    # Init DB (SQLite by default or DB_URL)
    from shared.storage.db import init_database, create_tables
    init_database()
    create_tables()

    # Persona + Question repositories
    from benchmark.repository.persona_repository import FullPersonaRepository
    from benchmark.repository.question import QuestionRepository

    persona_repo = FullPersonaRepository()
    if args.question_file:
        if not args.question_file.endswith(".csv") or not os.path.isfile(args.question_file):
            print("[fatal] --question-file must be a CSV file", file=sys.stderr)
            return 2
        question_repo = QuestionRepository(path=args.question_file)
    else:
        question_repo = QuestionRepository()

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
    else:
        if not args.hf_model:
            print("[fatal] --hf-model is required when --llm=hf", file=sys.stderr)
            return 2
        llm = LlmClientHFBench(model_name_or_path=args.hf_model, batch_size=args.batch_size)
        model_name = args.hf_model

    persist = BenchPersisterPrint() if args.persist == "print" else BenchPersisterPeewee()

    # Create a BenchmarkRun record to capture parameters for traceability
    from shared.storage import models as dbm
    try:
        bench_run = dbm.BenchmarkRun.create(
            gen_id=args.gen_id,
            llm_kind=args.llm,
            model_name=model_name,
            batch_size=args.batch_size,
            max_new_tokens=args.max_new_tokens,
            max_attempts=args.max_attempts,
            template_version="v1",
            include_rationale=include_rationale,
            system_prompt=args.system_prompt,
            question_file=args.question_file,
            persist_kind=args.persist,
        )
        benchmark_run_id = bench_run.id
    except Exception as e:
        print(f"[warn] failed to record BenchmarkRun: {e}", file=sys.stderr)
        benchmark_run_id = None  # still run pipeline

    run_benchmark_pipeline(
        gen_id=args.gen_id,
        question_repo=question_repo,
        persona_repo=persona_repo,
        prompt_factory=prompt_factory,
        llm=llm,
        post=post,
        persist=persist,
        model_name=model_name,
        benchmark_run_id=benchmark_run_id,
        max_attempts=args.max_attempts,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
