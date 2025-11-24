# apps/benchmark/src/benchmark/pipeline/adapters/postprocessor_likert.py
from __future__ import annotations

import logging

from ...ports_bench import (
    BenchAnswerDto,
    BenchPostProcessor,
    FailDecision,
    LLMResult,
    OkDecision,
    RetryDecision,
)
from .abstract_postprocessor import AbstractPostProcessor

_LOG = logging.getLogger(__name__)


class LikertPostProcessor(AbstractPostProcessor, BenchPostProcessor):
    use_llama_sanitize = True
    use_thinking_strip = True  # optional if models add "thinking" blocks

    def __init__(self, *, include_rationale: bool = True) -> None:
        self.include_rationale = include_rationale

    def strict_suffix(self) -> str:
        if self.include_rationale:
            return (
                "\nANTWORTE NUR als einzelnes JSON mit Schlüsseln 'rating' (1-5) und 'rationale'. "
                "KEINE Prosa, KEIN Markdown, KEINE weiteren Schlüssel."
            )
        return (
            "\nANTWORTE NUR als einzelnes JSON mit Schlüssel 'rating' (1-5). "
            "KEINE Prosa, KEIN Markdown, KEINE weiteren Schlüssel."
        )

    def build_ok(
        self,
        res: LLMResult,
        data,
        raw_text: str,
        attr_generation_run_id: int | None = None,
    ):
        if not isinstance(data, dict):
            raise ValueError("not_a_dict")

        # Check for unexpected rationale
        if not self.include_rationale and "rationale" in data:
            _LOG.warning(
                f"[LikertPostProcessor] UNEXPECTED RATIONALE found for persona={res.spec.work.persona_uuid} "
                f"attempt={res.spec.attempt}. Model returned rationale but prompt should not request it! "
                f"This might indicate vLLM cache pollution or prompt leak. Rationale: {data['rationale'][:100]}"
            )

        # Validate rating key exists
        if "rating" not in data:
            raise ValueError("missing_rating_key")

        rating_val = data.get("rating")

        # Validate rating is not null
        if rating_val is None:
            raise ValueError("rating_is_null")

        rating = None
        if isinstance(rating_val, (int, float)):
            rating_i = int(round(float(rating_val)))
            # Validate rating is in valid range
            if not (1 <= rating_i <= 5):
                raise ValueError(f"rating_out_of_range: {rating_i}")
            rating = rating_i
        else:
            raise ValueError(f"rating_not_numeric: {type(rating_val).__name__}")

        spec = res.spec
        ans = BenchAnswerDto(
            persona_uuid=spec.work.persona_uuid,
            case_id=spec.work.case_id,
            model_name=spec.model_name,
            template_version=spec.template_version,
            benchmark_run_id=spec.benchmark_run_id,
            attempt=spec.attempt,
            gen_time_ms=res.gen_time_ms,
            answer_raw=(raw_text[:2000] if raw_text else ""),
            rating=rating,
            scale_reversed=bool(getattr(spec.work, "scale_reversed", False)),
        )
        return OkDecision(kind="ok", answers=[ans])

    def build_retry(self, res: LLMResult, reason: str):
        return RetryDecision(kind="retry", reason=reason, retry_spec=res.spec)

    def build_fail(self, res: LLMResult, raw_text: str):
        return FailDecision(
            kind="fail", reason="unparseable_output", raw_text_snippet=raw_text
        )
