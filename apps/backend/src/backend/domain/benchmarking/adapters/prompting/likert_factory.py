from __future__ import annotations

from typing import Iterable

from ...ports_bench import BenchPromptFactory, BenchPromptSpec, BenchWorkItem
from .base import BasePromptFactory
from .utils_json import json_format_instruction_de, json_only_preamble_de
from .utils_persona import describe_persona_de, likert_5_de

DEFAULT_MAX_NEW_TOKENS = 160


class LikertPromptFactory(
    BasePromptFactory[BenchWorkItem, BenchPromptSpec], BenchPromptFactory
):
    def __init__(
        self,
        max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
        *,
        system_preamble: str | None = None,
        include_rationale: bool = True,
    ) -> None:
        super().__init__(spec_ctor=BenchPromptSpec, max_new_tokens=max_new_tokens)
        self._system_preamble = system_preamble
        self._include_rationale = include_rationale

    def system_preamble(self) -> str:
        if self._system_preamble:
            return self._system_preamble
        return json_only_preamble_de(
            "Du bist ein sorgfältiger Beurteiler. Lies die Personbeschreibung und die Frage."
        )

    def user_block(self, work: BenchWorkItem) -> str:
        persona_txt = describe_persona_de(work.persona_context)

        # Simplified question generation: use same adjective as Likert scale
        # and reference the persona's name when available.
        name = work.persona_context.get("name") or "die Person"
        adjective = work.adjective or ""
        question_text = f"Wie {adjective} wirkt {name}?".strip()

        likert_block = likert_5_de(
            adjective, reverse=bool(getattr(work, "scale_reversed", False))
        )

        if self._include_rationale:
            fmt = json_format_instruction_de(
                '{\n  "rating": <Ganzzahl 1-5>,\n  "rationale": "kurze Begründung in 1-2 Sätzen"\n}'
            )
            tail = (
                "Antworte ausschließlich mit einem einzigen JSON-Objekt in einer Zeile. "
                "Formatiere sehr knapp (Rationale höchstens 1 Satz, max. 18 Wörter).\n"
            )
        else:
            fmt = json_format_instruction_de('{\n  "rating": <Ganzzahl 1-5>\n}')
            tail = "Antworte ausschließlich mit einem einzigen JSON-Objekt in einer Zeile.\n"

        return (
            f"{persona_txt}\n\n"
            f"{question_text}\n\n"
            "Bitte wähle eine Antwort aus der folgenden Skala:\n"
            f"{likert_block}\n\n"
            f"{tail}"
            f"{fmt}"
        )

    # Override to thread benchmark_run_id into Spec
    def prompts(
        self,
        items: Iterable[BenchWorkItem],
        *,
        model_name: str,
        template_version: str,
        attempt: int,
        benchmark_run_id: int,
    ) -> Iterable[BenchPromptSpec]:
        pre = self.system_preamble()
        shots = self.few_shots()
        head = (pre + ("\n" + shots if shots else "")).strip()

        for w in items:
            body = self.user_block(w).strip()
            prompt = (head + "\n\n" + body).strip() if head else body
            yield BenchPromptSpec(
                work=w,
                prompt_text=prompt,
                max_new_tokens=self.max_new_tokens,
                attempt=attempt,
                model_name=model_name,
                template_version=template_version,
                benchmark_run_id=benchmark_run_id,
            )
