# apps/benchmark/src/benchmark/pipeline/preprocess.py
from __future__ import annotations
from typing import Iterable, List, Optional
from .ports import (
    PersonaRepo, PromptFactory, LLMClient, PostProcessor, Persister,
    WorkItem, PromptSpec, LLMResult, AttributeDto, FailureDto,
    OkDecision, RetryDecision, FailDecision,
)

_SNIP = 300

def _snippet(s: Optional[str], n: int = _SNIP) -> str:
    return s[:n] if s else ""

def _persist_fail(persist: Persister, spec: PromptSpec, kind: str, raw: str, reason: Optional[str] = None) -> None:
    persist.persist_failure(FailureDto(
        persona_uuid=spec.work.persona_uuid,
        model_name=spec.model_name,
        attempt=spec.attempt,
        error_kind=reason or kind,
        raw_text_snippet=_snippet(raw),
        prompt_snippet=_snippet(spec.prompt_text),
    ))

def run_preprocess_pipeline(
    *,
    gen_id: int,
    persona_repo: PersonaRepo,
    prompt_factory: PromptFactory,
    llm: LLMClient,
    post: PostProcessor,
    persist: Persister,
    model_name: str,
    template_version: str = "v1",
    max_attempts: int = 3,
    persist_buffer_size: int = 512,
) -> None:
    attempt = 1
    base_items: Iterable[WorkItem] = persona_repo.iter_personas(gen_id)
    pending_specs: Iterable[PromptSpec] = prompt_factory.prompts(
        base_items, model_name=model_name, template_version=template_version, attempt=attempt
    )

    attr_buf: List[AttributeDto] = []

    while attempt <= max_attempts:
        results: Iterable[LLMResult] = llm.run_stream(pending_specs)
        next_retry_specs: List[PromptSpec] = []

        for res in results:
            spec = res.spec
            decision = post.decide(res)

            if isinstance(decision, OkDecision):
                if not decision.attrs:
                    _persist_fail(persist, spec, "ok_without_attrs", res.raw_text)
                    continue
                attr_buf.extend(decision.attrs)
                if len(attr_buf) >= persist_buffer_size:
                    persist.persist_attributes(attr_buf)
                    attr_buf.clear()

            elif isinstance(decision, RetryDecision):
                next_retry_specs.append(decision.retry_spec)

            elif isinstance(decision, FailDecision):
                _persist_fail(persist, spec, decision.reason, decision.raw_text_snippet)

            else:
                _persist_fail(persist, spec, "unknown_decision", res.raw_text)

        if attr_buf:
            persist.persist_attributes(attr_buf)
            attr_buf.clear()

        if not next_retry_specs:
            break

        attempt += 1
        if attempt > max_attempts:
            for spec in next_retry_specs:
                _persist_fail(persist, spec, "max_attempts_exceeded", raw="")
            break

        pending_specs = iter(next_retry_specs)
