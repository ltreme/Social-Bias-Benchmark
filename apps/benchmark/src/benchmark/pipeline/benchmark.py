from __future__ import annotations
from typing import Iterable, List, Optional
import os

from .ports_bench import (
    BenchPersonaRepo,
    BenchPromptFactory,
    LLMClient,
    BenchPostProcessor,
    BenchPersister,
    BenchWorkItem,
    BenchPromptSpec,
    LLMResult,
    BenchAnswerDto,
)
from .ports import FailureDto  # reuse same FailureDto schema


_SNIP = 300


def _snippet(s: Optional[str], n: int = _SNIP) -> str:
    return s[:n] if s else ""


def _persist_fail(persist: BenchPersister, spec: BenchPromptSpec, kind: str, raw: str, reason: Optional[str] = None) -> None:
    persist.persist_failure(
        FailureDto(
            persona_uuid=spec.work.persona_uuid,
            model_name=spec.model_name,
            attempt=spec.attempt,
            error_kind=reason or kind,
            raw_text_snippet=_snippet(raw),
            prompt_snippet=_snippet(spec.prompt_text),
        )
    )


def run_benchmark_pipeline(
    *,
    gen_id: int,
    question_repo,
    persona_repo: BenchPersonaRepo,
    prompt_factory: BenchPromptFactory,
    llm: LLMClient,
    post: BenchPostProcessor,
    persist: BenchPersister,
    model_name: str,
    template_version: str = "v1",
    max_attempts: int = 3,
    persist_buffer_size: int = 512,
) -> None:
    """Primary benchmark pipeline.

    - Materializes the small set of questions once (≈30), keeping personas streamed.
    - Cross-joins lazily: for each persona, iterate over questions to yield work items.
    - Batches via the LLM client and persists in chunks.
    """

    # 1) Load questions once (small and stable)
    questions = list(question_repo.iter_all())

    def iter_items() -> Iterable[BenchWorkItem]:
        for p in persona_repo.iter_personas(gen_id):
            for q in questions:
                yield BenchWorkItem(
                    gen_id=p.gen_id,
                    persona_uuid=p.persona_uuid,
                    persona_context=p.persona_context,
                    question_uuid=q.uuid,
                    adjective=q.adjective,
                    question_template=q.question_template,
                )

    attempt = 1
    base_items: Iterable[BenchWorkItem] = iter_items()
    pending_specs: Iterable[BenchPromptSpec] = prompt_factory.prompts(
        base_items, model_name=model_name, template_version=template_version, attempt=attempt
    )

    # Note: We intentionally do NOT buffer persistence anymore. LLM batching remains.

    debug = os.getenv("BENCH_DEBUG", "").lower() in ("1", "true", "yes")
    while attempt <= max_attempts:
        results: Iterable[LLMResult] = llm.run_stream(pending_specs)
        next_retry_specs: List[BenchPromptSpec] = []
        ok_cnt = retry_cnt = fail_cnt = 0

        for res in results:
            spec = res.spec  # BenchPromptSpec
            decision = post.decide(res)

            if decision.kind == "ok":
                if not decision.answers:
                    _persist_fail(persist, spec, "ok_without_answer", res.raw_text)
                    continue
                # Persist immediately (no buffering in persister phase)
                persist.persist_results(decision.answers)
                if debug:
                    try:
                        a = decision.answers[0]
                        print(f"[BenchmarkPipeline] OK -> persisted persona={a.persona_uuid} question={a.question_uuid} rating={a.rating}")
                    except Exception:
                        pass
                ok_cnt += 1

            elif decision.kind == "retry":
                next_retry_specs.append(decision.retry_spec)
                retry_cnt += 1

            elif decision.kind == "fail":
                _persist_fail(persist, spec, decision.reason, decision.raw_text_snippet)
                fail_cnt += 1

            else:
                _persist_fail(persist, spec, "unknown_decision", res.raw_text)

        if debug:
            try:
                print(f"[BenchmarkPipeline] attempt={attempt} decisions ok={ok_cnt} retry={retry_cnt} fail={fail_cnt}")
            except Exception:
                pass

        if not next_retry_specs:
            break

        attempt += 1
        if attempt > max_attempts:
            for spec in next_retry_specs:
                _persist_fail(persist, spec, "max_attempts_exceeded", raw="")
            break

        pending_specs = iter(next_retry_specs)
