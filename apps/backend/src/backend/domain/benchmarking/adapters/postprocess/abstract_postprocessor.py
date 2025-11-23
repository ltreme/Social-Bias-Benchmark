# apps/benchmark/src/benchmark/pipeline/adapters/abstract_postprocessor.py
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import replace
from typing import Any

from ...ports import LLMResult  # adjust import if both ports/ports_bench used
from .utils.json_tools import (
    extract_first_json,
    sanitize_llama_chat,
    strip_thinking_blocks,
)

_LOG = logging.getLogger(__name__)


class AbstractPostProcessor(ABC):
    """Template for post-processors with shared sanitize/parse/retry logic."""

    attempt_limit: int = 2
    fail_snippet_len: int = 300
    debug_snippet_len: int = 200

    # Toggle sanitizer flags per subclass
    use_llama_sanitize: bool = False
    use_thinking_strip: bool = False

    @abstractmethod
    def strict_suffix(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def build_ok(
        self,
        res: LLMResult,
        data: Any,
        raw_text: str,
        attr_generation_run_id: int | None = None,
    ):
        raise NotImplementedError

    @abstractmethod
    def build_retry(self, res: LLMResult, reason: str):
        raise NotImplementedError

    @abstractmethod
    def build_fail(self, res: LLMResult, raw_text: str):
        raise NotImplementedError

    def sanitize(self, text: str) -> str:
        t = text or ""
        if self.use_llama_sanitize:
            t = sanitize_llama_chat(t)
        if self.use_thinking_strip:
            t = strip_thinking_blocks(t)
        return t.strip()

    def decide(self, res: LLMResult, attr_generation_run_id: int | None = None):
        spec = res.spec
        text = self.sanitize(res.raw_text or "")

        # Log only errors or unexpected outputs
        data = extract_first_json(text)
        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
            data = data[0]

        if isinstance(data, (dict, list)):
            try:
                return self.build_ok(res, data, text, attr_generation_run_id)
            except Exception as e:
                _LOG.warning(
                    f"[{self.__class__.__name__}] Validation error for persona={spec.work.persona_uuid}: {type(e).__name__}"
                )

        if spec.attempt < self.attempt_limit:
            stricter = replace(
                spec,
                attempt=spec.attempt + 1,
                prompt_text=spec.prompt_text + self.strict_suffix(),
            )
            return self.build_retry(
                type(res)(
                    spec=stricter, raw_text=res.raw_text, gen_time_ms=res.gen_time_ms
                ),
                reason="parse_error",
            )

        return self.build_fail(res, raw_text=text[: self.fail_snippet_len])
