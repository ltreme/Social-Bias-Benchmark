# apps/benchmark/src/benchmark/pipeline/adapters/postprocessor_attr.py
from __future__ import annotations
import json
from json import JSONDecoder
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

    def _strip_code_fences(self, s: str) -> str:
        t = s.strip()
        # remove ```json ... ``` or ``` ... ``` fences if present
        if t.startswith("```") and t.endswith("```"):
            t = t.strip("`")  # drop surrounding backticks
            # after stripping, there might be a leading language tag like json\n
            # find first newline and keep the rest
            nl = t.find("\n")
            if nl != -1:
                t = t[nl + 1 :]
        return t.strip()

    def _extract_first_json_obj(self, s: str):
        """
        Be tolerant with chatty outputs: accept the first JSON object in the text,
        even if there is trailing content before/after it.
        Returns a Python object or raises on failure.
        """
        text = self._strip_code_fences(s)

        # 1) direct parse
        try:
            return json.loads(text)
        except Exception:
            pass

        # 2) raw_decode from start (ignores trailing content)
        dec = JSONDecoder()
        try:
            obj, _end = dec.raw_decode(text.lstrip())
            return obj
        except Exception:
            pass

        # 3) find first '{' and raw_decode from there
        i = text.find("{")
        if i != -1:
            try:
                obj, _end = dec.raw_decode(text[i:])
                return obj
            except Exception:
                pass

        # 4) Sometimes models emit a single-element list with the object
        i = text.find("[")
        if i != -1:
            try:
                obj, _end = dec.raw_decode(text[i:])
                return obj
            except Exception:
                pass

        # give up
        raise ValueError("no_json_found")

    def decide(self, res: LLMResult) -> Decision:
        spec = res.spec
        text = res.raw_text

        # helpful debug
        print(f"persona={spec.work.persona_uuid} attempt={spec.attempt} raw_snippet={(text or '')[:160]!r}")

        try:
            data = self._extract_first_json_obj(text)
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
            print(f"OK persona={spec.work.persona_uuid} keys={[a.attribute_key for a in attrs]}")
            return OkDecision(kind=DecisionKind.OK, attrs=attrs)

        except Exception as e:
            print(f"PARSE_FAIL persona={spec.work.persona_uuid} err={type(e).__name__}")
            if spec.attempt < 2:
                stricter = replace(spec, attempt=spec.attempt + 1, prompt_text=spec.prompt_text + self.strict_suffix)
                return RetryDecision(kind=DecisionKind.RETRY, reason=f"parse_error:{type(e).__name__}", retry_spec=stricter)
            return FailDecision(kind=DecisionKind.FAIL, reason="unparseable_output", raw_text_snippet=(text or "")[:300])
