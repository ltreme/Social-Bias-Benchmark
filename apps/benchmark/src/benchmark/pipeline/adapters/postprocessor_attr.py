# apps/benchmark/src/benchmark/pipeline/adapters/postprocessor_attr.py
from __future__ import annotations
import json
from dataclasses import replace
from typing import List
from ..ports import (
    PostProcessor, LLMResult, Decision, DecisionKind,
    OkDecision, RetryDecision, FailDecision, AttributeDto,
)

class AttributePostProcessor(PostProcessor):
    def __init__(self, require_keys: List[str] | None = None, strict_suffix: str | None = None):
        self.require_keys = require_keys or ["name", "appearance", "biography"]
        self.strict_suffix = strict_suffix or "\nSTRICT: JSON ONLY. No commentary. Keys: name, appearance, biography."

    def decide(self, res: LLMResult) -> Decision:
        spec = res.spec
        text = res.raw_text

        print("Raw text:", text)

        try:
            data = json.loads(text)
            if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
                data = data[0]
            if not isinstance(data, dict):
                raise ValueError("not_a_dict")

            missing = [k for k in self.require_keys if k not in data or not str(data[k]).strip()]
            if missing:
                raise KeyError(f"missing_keys:{missing}")

            attrs = [
                AttributeDto(spec.work.persona_uuid, "name", str(data["name"]), spec.model_name, res.gen_time_ms, spec.attempt),
                AttributeDto(spec.work.persona_uuid, "appearance", str(data["appearance"]), spec.model_name, res.gen_time_ms, spec.attempt),
                AttributeDto(spec.work.persona_uuid, "biography", str(data["biography"]), spec.model_name, res.gen_time_ms, spec.attempt),
            ]
            return OkDecision(kind=DecisionKind.OK, attrs=attrs)

        except Exception as e:
            if spec.attempt < 2:
                stricter = replace(spec, attempt=spec.attempt + 1, prompt_text=spec.prompt_text + self.strict_suffix)
                return RetryDecision(kind=DecisionKind.RETRY, reason=f"parse_error:{type(e).__name__}", retry_spec=stricter)
            return FailDecision(kind=DecisionKind.FAIL, reason="unparseable_output", raw_text_snippet=(text or "")[:300])
