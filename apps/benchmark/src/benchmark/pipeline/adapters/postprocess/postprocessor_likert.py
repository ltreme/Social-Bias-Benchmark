# apps/benchmark/src/benchmark/pipeline/adapters/postprocessor_likert.py
from __future__ import annotations
from ...ports_bench import (
    BenchPostProcessor,
    LLMResult,
    OkDecision,
    RetryDecision,
    FailDecision,
    BenchAnswerDto,
)
from .abstract_postprocessor import AbstractPostProcessor


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

    def build_ok(self, res: LLMResult, data, raw_text: str):
        if not isinstance(data, dict):
            raise ValueError("not_a_dict")
        rating_val = data.get("rating")
        rating = None
        if isinstance(rating_val, (int, float)):
            rating_i = int(round(float(rating_val)))
            if 1 <= rating_i <= 5:
                rating = rating_i

        spec = res.spec
        ans = BenchAnswerDto(
            persona_uuid=spec.work.persona_uuid,
            question_uuid=spec.work.question_uuid,
            model_name=spec.model_name,
            template_version=spec.template_version,
            benchmark_run_id=spec.benchmark_run_id,
            attempt=spec.attempt,
            gen_time_ms=res.gen_time_ms,
            answer_raw=(raw_text[:2000] if raw_text else ""),
            rating=rating,
        )
        return OkDecision(kind="ok", answers=[ans])

    def build_retry(self, res: LLMResult, reason: str):
        return RetryDecision(kind="retry", reason=reason, retry_spec=res.spec)

    def build_fail(self, res: LLMResult, raw_text: str):
        return FailDecision(kind="fail", reason="unparseable_output", raw_text_snippet=raw_text)
