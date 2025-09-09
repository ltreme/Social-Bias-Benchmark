from __future__ import annotations
from ...ports import (
    PostProcessor,
    LLMResult,
    DecisionKind,
    OkDecision,
    RetryDecision,
    FailDecision,
    AttributeDto,
)
from .abstract_postprocessor import AbstractPostProcessor


class AttributePostProcessor(AbstractPostProcessor, PostProcessor):
    use_llama_sanitize = False
    use_thinking_strip = False

    def __init__(self, require_keys: list[str] | None = None):
        self.require_keys = require_keys or ["name", "appearance", "biography"]

    def strict_suffix(self) -> str:
        return "\nSTRICT: JSON ONLY. No commentary. Keys: name, appearance, biography."

    def build_ok(self, res: LLMResult, data, raw_text: str):
        if not isinstance(data, dict):
            raise ValueError("not_a_dict")
        missing = [k for k in self.require_keys if k not in data or not str(data[k]).strip()]
        if missing:
            raise KeyError(f"missing_keys:{missing}")

        spec = res.spec
        attrs = [
            AttributeDto(
                spec.work.persona_uuid, "name", str(data["name"]), spec.model_name, res.gen_time_ms, spec.attempt
            ),
            AttributeDto(
                spec.work.persona_uuid,
                "appearance",
                str(data["appearance"]),
                spec.model_name,
                res.gen_time_ms,
                spec.attempt,
            ),
            AttributeDto(
                spec.work.persona_uuid,
                "biography",
                str(data["biography"]),
                spec.model_name,
                res.gen_time_ms,
                spec.attempt,
            ),
        ]
        print(f"[AttributePostProcessor] OK keys={[a.attribute_key for a in attrs]}")
        return OkDecision(kind=DecisionKind.OK, attrs=attrs)

    def build_retry(self, res: LLMResult, reason: str):
        return RetryDecision(kind=DecisionKind.RETRY, reason=reason, retry_spec=res.spec)

    def build_fail(self, res: LLMResult, raw_text: str):
        return FailDecision(kind=DecisionKind.FAIL, reason="unparseable_output", raw_text_snippet=raw_text)
