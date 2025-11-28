from __future__ import annotations

import os
import time
from typing import Iterable, List, Optional

from .ports import (
    AttributeDto,
    FailDecision,
    FailureDto,
    LLMClient,
    LLMResult,
    OkDecision,
    Persister,
    PersonaRepo,
    PostProcessor,
    PromptFactory,
    PromptSpec,
    RetryDecision,
    WorkItem,
)

_SNIP = 300


def _snippet(s: Optional[str], n: int = _SNIP) -> str:
    return s[:n] if s else ""


def _persist_fail(
    persist: Persister,
    spec: PromptSpec,
    kind: str,
    raw: str,
    reason: Optional[str] = None,
) -> None:
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


def run_attr_gen_pipeline(
    *,
    dataset_id: int | None,
    persona_repo: PersonaRepo,
    prompt_factory: PromptFactory,
    llm: LLMClient,
    post: PostProcessor,
    persist: Persister,
    model_name: str,
    template_version: str = "v1",
    max_attempts: int = 3,
    persist_buffer_size: int = 512,
    total_personas_override: int | None = None,
    attr_generation_run_id: int | None = None,
) -> None:
    # Progress setup
    if total_personas_override is not None:
        total_personas = int(total_personas_override)
    else:
        total_personas = 0
        count_method = getattr(persona_repo, "count", None)
        if callable(count_method):
            try:
                total_personas = int(count_method(dataset_id))
            except Exception:
                total_personas = 0

    # Determine progress frequency based on batch size with sensible defaults.
    def _compute_progress_every(
        batch_size: int | None, env_var: str, baseline: int = 10
    ) -> int:
        # Allow explicit override via env var
        env_val = os.getenv(env_var)
        if env_val is not None:
            try:
                return max(1, int(env_val))
            except Exception:
                pass
        # Fallback: derive from batch size
        if not batch_size or batch_size <= 0:
            return baseline
        if batch_size >= baseline:
            return batch_size
        # Choose the multiple of batch_size closest to baseline; ties choose smaller
        # Using bankers rounding achieves the tie-break toward smaller for x.5
        k = max(1, round(baseline / batch_size))
        return max(1, batch_size * k)

    progress_every = _compute_progress_every(
        getattr(llm, "batch_size", None), "ATTR_PROGRESS_EVERY", 10
    )
    progress_log = os.getenv("ATTRGEN_PROGRESS_LOG", "").lower() in ("1", "true", "yes")
    done_personas: set[str] = set()
    t0 = time.perf_counter()

    def _fmt_dur(seconds: float) -> str:
        s = int(seconds)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}h{m:02d}m{s:02d}s"
        if m:
            return f"{m}m{s:02d}s"
        return f"{s}s"

    attempt = 1
    base_items: Iterable[WorkItem] = persona_repo.iter_personas(dataset_id)
    pending_specs: Iterable[PromptSpec] = prompt_factory.prompts(
        base_items,
        model_name=model_name,
        template_version=template_version,
        attempt=attempt,
    )

    attr_buf: List[AttributeDto] = []

    # Token usage tracking
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens_used = 0

    while attempt <= max_attempts:
        results: Iterable[LLMResult] = llm.run_stream(pending_specs)
        next_retry_specs: List[PromptSpec] = []

        for res in results:
            # Accumulate token usage
            if res.prompt_tokens is not None:
                total_prompt_tokens += res.prompt_tokens
            if res.completion_tokens is not None:
                total_completion_tokens += res.completion_tokens
            if res.total_tokens is not None:
                total_tokens_used += res.total_tokens

            spec = res.spec
            decision = post.decide(res, attr_generation_run_id)

            if isinstance(decision, OkDecision):
                if not decision.attrs:
                    _persist_fail(persist, spec, "ok_without_attrs", res.raw_text)
                    continue
                attr_buf.extend(decision.attrs)
                # Mark persona finished on first OK
                puid = str(spec.work.persona_uuid)
                if puid not in done_personas:
                    done_personas.add(puid)
                    if progress_log and (
                        (len(done_personas) % progress_every == 0)
                        or (total_personas and len(done_personas) == total_personas)
                    ):
                        pct = (
                            100.0 * len(done_personas) / total_personas
                            if total_personas
                            else 0.0
                        )
                        elapsed = _fmt_dur(time.perf_counter() - t0)
                        print(
                            f"[AttrGen] progress: {len(done_personas)}/{total_personas or '?'} personas ({pct:.1f}%), elapsed={elapsed}"
                        )
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
                # Count remaining as finished (failed permanently)
                puid = str(spec.work.persona_uuid)
                if puid not in done_personas:
                    done_personas.add(puid)
            if progress_log and done_personas:
                pct = (
                    100.0 * len(done_personas) / total_personas
                    if total_personas
                    else 0.0
                )
                elapsed = _fmt_dur(time.perf_counter() - t0)
                print(
                    f"[AttrGen] progress: {len(done_personas)}/{total_personas or '?'} personas ({pct:.1f}%), elapsed={elapsed}"
                )
            break

        pending_specs = iter(next_retry_specs)

    # Update token usage in database at the end
    if total_tokens_used > 0 and attr_generation_run_id is not None:
        try:
            persist.update_token_usage(
                attr_generation_run_id=attr_generation_run_id,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                total_tokens=total_tokens_used,
            )
            print(
                f"[AttrGen] Token usage: prompt={total_prompt_tokens:,}, "
                f"completion={total_completion_tokens:,}, total={total_tokens_used:,}"
            )
        except Exception as e:
            import logging

            _LOG = logging.getLogger(__name__)
            _LOG.warning(f"[AttrGen] Failed to update token usage: {e}")
