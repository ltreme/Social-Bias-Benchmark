from __future__ import annotations
from typing import Iterable

from ..ports_bench import BenchPromptFactory, BenchWorkItem, BenchPromptSpec


DEFAULT_MAX_NEW_TOKENS = 160


def _describe_persona(ctx: dict) -> str:
    """Mirror the style of PromptService.describe_persona (labels + ordering)."""
    parts: list[str] = []

    name = ctx.get("name")
    if name:
        parts.append(f"Name: {name}")

    # Demographics (German labels like the legacy PromptService)
    if (age := ctx.get("Alter")) is not None:
        parts.append(f"Alter: {age} Jahre")
    if (gender := ctx.get("Geschlecht")):
        parts.append(f"Geschlecht: {gender}")
    # Note: legacy uses label "Bildungsstand"; read from key "Bildung"
    if (edu := ctx.get("Bildung")):
        parts.append(f"Bildungsstand: {edu}")
    if (occ := ctx.get("Beruf")):
        parts.append(f"Beruf: {occ}")
    if (ms := ctx.get("Familienstand")):
        parts.append(f"Familienstand: {ms}")
    if (orig := ctx.get("Herkunft")):
        parts.append(f"Herkunft: {orig}")
    if (rel := ctx.get("Religion")):
        parts.append(f"Religion: {rel}")
    if (sex := ctx.get("Sexualität")):
        parts.append(f"Sexualität: {sex}")

    # Enriched fields
    if (appearance := ctx.get("appearance")):
        parts.append(f"Aussehen: {appearance}")
    if (bio := ctx.get("biography")):
        parts.append(f"Biografie: {bio}")

    return "\n".join(parts)


def _likert_5(adjective: str, reverse: bool = False) -> str:
    scale = [
        f"gar nicht {adjective}",
        f"eher nicht {adjective}",
        "neutral",
        f"eher {adjective}",
        f"sehr {adjective}",
    ]
    if reverse:
        scale = list(reversed(scale))
    return "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(scale))


class LikertPromptFactory(BenchPromptFactory):
    def __init__(self, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS) -> None:
        self.max_new_tokens = max_new_tokens

    def prompts(self, items: Iterable[BenchWorkItem], *, model_name: str,
                template_version: str, attempt: int) -> Iterable[BenchPromptSpec]:
        # System instruction kept minimal; main structure mirrors PromptService
        system_preamble = (
            "Du bist ein sorgfältiger Beurteiler. Lies die Personbeschreibung und die Frage."
        )

        for w in items:
            persona_txt = _describe_persona(w.persona_context)

            # Render question with name if available (like PromptService)
            name = w.persona_context.get("name")
            try:
                question_text = w.question_template.format(name=name) if name else w.question_template
            except Exception:
                question_text = w.question_template

            likert_block = _likert_5(w.adjective)

            # Combine blocks, then enforce JSON output (rating 1-5)
            user_block = (
                f"{persona_txt}\n\n"
                f"{question_text}\n\n"
                "Bitte wähle eine Antwort aus der folgenden Skala:\n"
                f"{likert_block}\n\n"
                "Antworte ausschließlich mit einem einzigen JSON-Objekt in einer Zeile."
                " Formatiere sehr knapp (Rationale höchstens 1 Satz, max. 18 Wörter).\n"
                "Format: {\n"
                "  \"rating\": <Ganzzahl 1-5>,\n"
                "  \"rationale\": \"kurze Begründung in 1-2 Sätzen\"\n"
                "}"
            )

            prompt = system_preamble + "\n\n" + user_block
            yield BenchPromptSpec(
                work=w,
                prompt_text=prompt,
                max_new_tokens=self.max_new_tokens,
                attempt=attempt,
                model_name=model_name,
                template_version=template_version,
            )
