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
    p.add_argument("--template-version", type=str, default="v1")
    p.add_argument("--max-attempts", type=int, default=2)
    p.add_argument("--llm", choices=["fake", "hf"], default="fake")
    p.add_argument("--hf-model", type=str, help="HF model name/path (when --llm=hf)")
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--persist", choices=["print", "peewee"], default="print")
    p.add_argument("--max-new-tokens", type=int, default=256)
    p.add_argument("--question-file", type=str, help="Path to question file (csv)")
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

    prompt_factory = LikertPromptFactory(max_new_tokens=args.max_new_tokens)
    post = LikertPostProcessor()

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

    run_benchmark_pipeline(
        gen_id=args.gen_id,
        question_repo=question_repo,
        persona_repo=persona_repo,
        prompt_factory=prompt_factory,
        llm=llm,
        post=post,
        persist=persist,
        model_name=model_name,
        template_version=args.template_version,
        max_attempts=args.max_attempts,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
