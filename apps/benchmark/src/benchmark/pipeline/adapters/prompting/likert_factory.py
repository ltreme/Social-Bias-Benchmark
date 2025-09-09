from __future__ import annotations
from typing import Iterable

from ...ports_bench import BenchPromptFactory, BenchWorkItem, BenchPromptSpec
from .base import BasePromptFactory
from .utils_persona import describe_persona_de, likert_5_de
from .utils_json import json_only_preamble_de, json_format_instruction_de

DEFAULT_MAX_NEW_TOKENS = 160

class LikertPromptFactory(BasePromptFactory[BenchWorkItem, BenchPromptSpec], BenchPromptFactory):
    def __init__(self, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS) -> None:
        super().__init__(spec_ctor=BenchPromptSpec, max_new_tokens=max_new_tokens)

    def system_preamble(self) -> str:
        return json_only_preamble_de("Du bist ein sorgfältiger Beurteiler. Lies die Personbeschreibung und die Frage.")

    def user_block(self, work: BenchWorkItem) -> str:
        persona_txt = describe_persona_de(work.persona_context)

        # Render question with name if available
        name = work.persona_context.get("name")
        try:
            question_text = work.question_template.format(name=name) if name else work.question_template
        except Exception:
            question_text = work.question_template

        likert_block = likert_5_de(work.adjective)

        fmt = json_format_instruction_de(
            '{\n  "rating": <Ganzzahl 1-5>,\n  "rationale": "kurze Begründung in 1-2 Sätzen"\n}'
        )

        return (
            f"{persona_txt}\n\n"
            f"{question_text}\n\n"
            "Bitte wähle eine Antwort aus der folgenden Skala:\n"
            f"{likert_block}\n\n"
            "Antworte ausschließlich mit einem einzigen JSON-Objekt in einer Zeile. "
            "Formatiere sehr knapp (Rationale höchstens 1 Satz, max. 18 Wörter).\n"
            f"{fmt}"
        )
