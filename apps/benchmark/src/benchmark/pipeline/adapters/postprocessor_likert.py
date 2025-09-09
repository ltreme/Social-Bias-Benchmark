from __future__ import annotations
import json
from dataclasses import replace

from ..ports_bench import (
    BenchPostProcessor,
    LLMResult,
    OkDecision,
    RetryDecision,
    FailDecision,
    BenchAnswerDto,
)


def _extract_first_json_object(s: str) -> dict | None:
    """Extract the first top-level JSON object from mixed model output.
    Finds the first '{' and matches braces while respecting strings.
    """
    if not s:
        return None
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i, ch in enumerate(s[start:], start=start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start:i + 1])
                    except Exception:
                        return None
    return None


class LikertPostProcessor(BenchPostProcessor):
    def __init__(self) -> None:
        # push model to stricter behavior on retry
        self.strict_suffix = (
            "\nANTWORTE NUR als einzelnes JSON mit Schlüsseln 'rating' (1-5) und 'rationale'. "
            "KEINE Prosa, KEIN Markdown, KEINE weiteren Schlüssel."
        )

    def _sanitize_llama_chat(self, text: str) -> str:
        """Heuristic cleanup for Llama chat artifacts.
        Cuts everything up to and including the last chat close marker, then trims.
        """
        if not text:
            return text
        # Candidates seen in outputs
        candidates = ['[/INST]', '/INST]']
        match = None
        pos = -1
        for token in candidates:
            p = text.rfind(token)
            if p > pos:
                pos = p
                match = token
        if pos != -1 and match is not None:
            cleaned = text[pos + len(match):]
            # Some models leave a stray ']' or spaces right after the marker
            return cleaned.lstrip(' \t\n\r]')
        return text

    def decide(self, res: LLMResult):
        spec = res.spec
        text = res.raw_text or ""
        text = self._sanitize_llama_chat(text)

        # Debug logging to inspect raw generations
        try:
            # Also show persona name to cross-check prompt content
            name_dbg = spec.work.persona_context.get("name") if hasattr(spec.work, "persona_context") else None
            print("[LikertPostProcessor] raw_text snippet:", (text or "")[:200].replace("\n", "\\n"))
            if name_dbg:
                print(f"[LikertPostProcessor] persona in prompt: {name_dbg}")
        except Exception:
            pass

        data = _extract_first_json_object(text)
        if data is None:
            # Fallback: direct parse (handles exact JSON-only outputs)
            try:
                data = json.loads(text)
            except Exception:
                data = None
        if not isinstance(data, dict):
            data = None

        if data is not None:
            rating_val = data.get("rating") if isinstance(data, dict) else None
            rating: int | None = None
            if isinstance(rating_val, (int, float)):
                rating_i = int(round(float(rating_val)))
                if 1 <= rating_i <= 5:
                    rating = rating_i

            ans = BenchAnswerDto(
                persona_uuid=spec.work.persona_uuid,
                question_uuid=spec.work.question_uuid,
                model_name=spec.model_name,
                template_version=spec.template_version,
                attempt=spec.attempt,
                gen_time_ms=res.gen_time_ms,
                answer_raw=(text[:2000] if text else ""),
                rating=rating,
            )
            # Extra debug for successful parses
            import os
            if os.getenv("BENCH_DEBUG", "").lower() in ("1", "true", "yes"):
                try:
                    print(f"[LikertPostProcessor] parsed OK: persona={ans.persona_uuid} question={ans.question_uuid} rating={ans.rating}")
                except Exception:
                    pass
            return OkDecision(kind="ok", answers=[ans])

        # one retry with stricter instruction
        if spec.attempt < 2:
            stricter = replace(spec, attempt=spec.attempt + 1, prompt_text=spec.prompt_text + self.strict_suffix)
            return RetryDecision(kind="retry", reason="parse_error", retry_spec=stricter)
        return FailDecision(kind="fail", reason="unparseable_output", raw_text_snippet=text[:300])
