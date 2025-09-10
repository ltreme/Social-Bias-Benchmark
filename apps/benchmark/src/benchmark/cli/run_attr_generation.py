from __future__ import annotations
import argparse, sys

from benchmark.pipeline.attr_gen import run_attr_gen_pipeline
from benchmark.pipeline.adapters.prompting import AttributePromptFactory
from benchmark.pipeline.adapters.postprocess.postprocessor_attr import AttributePostProcessor
from benchmark.pipeline.adapters.persister_sqlite import PersisterPrint, PersisterPeewee
from benchmark.pipeline.adapters.llm import LlmClientFake, LlmClientHF

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run preprocessing pipeline.")
    p.add_argument("--gen-id", type=int, required=True)
    # Optional: override the system prompt preamble
    p.add_argument("--system-prompt", type=str, help="Override system prompt/preamble")
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--max-new-tokens", type=int, default=192)
    p.add_argument("--persist-buffer-size", type=int, default=256)
    p.add_argument("--llm", choices=["fake", "hf"], default="hf")
    p.add_argument("--hf-model", type=str, help="HF model name/path (when --llm=hf)")
    p.add_argument("--batch-size", type=int, default=2)
    p.add_argument("--persist", choices=["print", "peewee"], default="peewee")
    args = p.parse_args(argv)

    # Init DB (SQLite default or DB_URL)
    from shared.storage.db import init_database, create_tables
    init_database()
    create_tables()

    # Persona source from shared
    from benchmark.repository.persona_repository import PersonaRepository
    persona_repo = PersonaRepository()

    prompt_factory = AttributePromptFactory(
        max_new_tokens=args.max_new_tokens,
        system_preamble=args.system_prompt,
    )
    post = AttributePostProcessor()

    if args.llm == "fake":
        llm = LlmClientFake(batch_size=args.batch_size)
        model_name = "fake"
    else:
        if not args.hf_model:
            print("[fatal] --hf-model is required when --llm=hf", file=sys.stderr)
            return 2
        llm = LlmClientHF(model_name_or_path=args.hf_model, batch_size=args.batch_size)
        model_name = args.hf_model

    persist = PersisterPrint() if args.persist == "print" else PersisterPeewee()

    # Record run parameters for attribute generation
    from shared.storage import models as dbm
    try:
        dbm.AttrGenerationRun.create(
            gen_id=args.gen_id,
            llm_kind=args.llm,
            model_name=model_name,
            batch_size=args.batch_size,
            max_new_tokens=args.max_new_tokens,
            max_attempts=args.max_attempts,
            persist_buffer_size=args.persist_buffer_size,
            template_version="v1",
            system_prompt=args.system_prompt,
            persist_kind=args.persist,
        )
    except Exception as e:
        print(f"[warn] failed to record AttrGenerationRun: {e}", file=sys.stderr)

    run_attr_gen_pipeline(
        gen_id=args.gen_id,
        persona_repo=persona_repo,
        prompt_factory=prompt_factory,
        llm=llm,
        post=post,
        persist=persist,
        model_name=model_name,  # automatisch gesetzt
        max_attempts=args.max_attempts,
        persist_buffer_size=args.persist_buffer_size,
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
