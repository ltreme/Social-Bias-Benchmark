from __future__ import annotations
import argparse, sys

from benchmark.pipeline.attr_gen import run_attr_gen_pipeline
from benchmark.pipeline.adapters.prompting import AttributePromptFactory
from benchmark.pipeline.adapters.postprocess.postprocessor_attr import AttributePostProcessor
from benchmark.pipeline.adapters.persister_sqlite import PersisterPrint, PersisterPeewee
from benchmark.pipeline.adapters.llm import (
    LlmClientFake,
    LlmClientVLLM,
)

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run preprocessing pipeline.")
    p.add_argument("--gen-id", type=int, required=False, help="DEPRECATED: Use --dataset-id instead. Persona generation run id (ignored when --dataset-id is set)")
    p.add_argument("--dataset-id", type=int, required=False, help="Run only for personas in the given Dataset")
    # Optional: override the system prompt preamble
    p.add_argument("--system-prompt", type=str, help="Override system prompt/preamble")
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--max-new-tokens", type=int, default=192)
    p.add_argument("--persist-buffer-size", type=int, default=256)
    p.add_argument("--llm", choices=["fake", "vllm"], default="vllm",
                help="LLM backend: vllm (preferred), or fake (testing)")
    # vLLM OpenAI-compatible server options
    p.add_argument("--vllm-base-url", type=str, default="http://localhost:8000",
                help="Base URL of vLLM server root (e.g., http://host:port)")
    p.add_argument("--vllm-model", type=str, help="Model name served by vLLM (when --llm=vllm)")
    p.add_argument("--vllm-api-key", type=str, default=None, help="Optional API key for vLLM server")
    p.add_argument("--batch-size", type=int, default=2)
    p.add_argument("--persist", choices=["print", "peewee"], default="peewee")
    args = p.parse_args(argv)

    # Init DB (SQLite default or DB_URL)
    from shared.storage.db import init_database, create_tables
    init_database()
    create_tables()

    # Persona source from shared
    from benchmark.repository.persona_repository import PersonaRepository, PersonaRepositoryByDataset
    persona_repo = PersonaRepository()
    total_override = None
    if args.dataset_id is not None:
        # Stream only personas in dataset
        persona_repo = PersonaRepositoryByDataset(dataset_id=int(args.dataset_id))
        try:
            from shared.storage.models import DatasetPersona
            total_override = DatasetPersona.select().where(DatasetPersona.dataset_id == int(args.dataset_id)).count()
        except Exception as e:
            print(f"[warn] could not count personas in dataset: {e}", file=sys.stderr)

    prompt_factory = AttributePromptFactory(
        max_new_tokens=args.max_new_tokens,
        system_preamble=args.system_prompt,
    )
    post = AttributePostProcessor()

    if args.llm == "fake":
        llm = LlmClientFake(batch_size=args.batch_size)
        model_name = "fake"
    else:  # vllm
        if not args.vllm_model:
            print("[fatal] --vllm-model is required when --llm=vllm", file=sys.stderr)
            return 2
        llm = LlmClientVLLM(
            base_url=args.vllm_base_url,
            model=args.vllm_model,
            api_key=args.vllm_api_key,
            batch_size=args.batch_size,
            max_new_tokens_cap=args.max_new_tokens,
        )
        model_name = args.vllm_model

    persist = PersisterPrint() if args.persist == "print" else PersisterPeewee()

    # Record run parameters for attribute generation
    from shared.storage import models as dbm
    attr_generation_run_id = None
    try:
        # Get or create model entry
        model_entry = dbm.Model.get_or_create(name=model_name)[0]
        run_entry = dbm.AttrGenerationRun.create(
            dataset_id=args.dataset_id,
            model_id=model_entry.id,
            batch_size=args.batch_size,
            max_new_tokens=args.max_new_tokens,
            max_attempts=args.max_attempts,
            system_prompt=args.system_prompt,
        )
        attr_generation_run_id = run_entry.id
    except Exception as e:
        print(f"[warn] failed to record AttrGenerationRun: {e}", file=sys.stderr)

    run_attr_gen_pipeline(
        dataset_id=args.dataset_id,
        persona_repo=persona_repo,
        prompt_factory=prompt_factory,
        llm=llm,
        post=post,
        persist=persist,
        model_name=model_name,  # automatisch gesetzt
        max_attempts=args.max_attempts,
        persist_buffer_size=args.persist_buffer_size,
        total_personas_override=total_override,
        attr_generation_run_id=attr_generation_run_id,
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
