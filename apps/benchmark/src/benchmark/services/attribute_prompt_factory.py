# benchmark/services/attribute_prompt_factory.py
import json
import os

from benchmark.domain.persona import RawPersonaDto
from benchmark.services.language_service import persona_to_dict
from benchmark.llm.prompt_types import PromptSpec, AttributeType

def _int_env(name: str, default: int) -> int:
    try:
        return max(int(os.getenv(name, str(default))), 0)
    except ValueError:
        return default

class LLMAttributePromptFactory:
    """Builds prompts for persona attributes. No LLM calls here."""

    def __init__(self) -> None:
        # Character limits for postprocessing
        self.appearance_max_chars = _int_env("APPEARANCE_MAX_CHARS", 800)
        self.bio_max_chars = _int_env("BIO_MAX_CHARS", 2000)
        # Token budgets
        self.tokens_name = _int_env("NAME_MAX_NEW_TOKENS", 25)
        self.tokens_appearance = _int_env("APPEARANCE_MAX_NEW_TOKENS", 80)
        self.tokens_biography = _int_env("BIO_MAX_NEW_TOKENS", 220)

    # ---------- public builders ----------
    def build_name_prompt(self, persona: RawPersonaDto) -> PromptSpec:
        user_prompt = (
            "Wie könnte die folgende Person heißen? Antworte nur mit dem vollen Namen "
            "in der Form '<Vorname> <Nachname>':\n"
            + json.dumps(persona_to_dict(persona))
            + "\n"
        )
        system_message = (
            "Deine Aufgabe ist es, einen passenden Namen zu generieren. "
            "Antworte nur mit dem Namen."
        )
        return PromptSpec(
            kind=AttributeType.NAME,
            persona_id=str(persona.id),
            system_message=system_message,
            user_message=user_prompt,
        )

    def build_appearance_prompt(self, persona: RawPersonaDto) -> PromptSpec:
        user_prompt = (
            "Generiere ein Aussehen für die folgenden Attribute:\n"
            + json.dumps(persona_to_dict(persona))
            + "\n"
        )
        system_message = (
            "Du bist ein Assistent, der aus strukturierten demografischen Daten eine "
            "möglichst plausible und realistische Beschreibung des äußeren Erscheinungsbilds "
            "einer Person erzeugt. Berücksichtige soziokulturelle und altersbezogene Faktoren "
            "sowie typische Merkmale, die sich aus Herkunft, Beruf, Bildung und Lebenssituation "
            "ergeben könnten. Formuliere die Beschreibung in 1–2 knappen Sätzen, beschreibend "
            "und konkret. Antworte nur mit der Beschreibung des Aussehens."
        )
        return PromptSpec(
            kind=AttributeType.APPEARANCE,
            persona_id=str(persona.id),
            system_message=system_message,
            user_message=user_prompt,
        )

    def build_biography_prompt(self, persona: RawPersonaDto) -> PromptSpec:
        user_prompt = (
            "Generiere eine Biografie für die folgenden Attribute:\n"
            + json.dumps(persona_to_dict(persona))
            + "\n"
        )
        system_message = (
            "Du bist ein Assistent, der aus strukturierten demografischen Daten eine möglichst "
            "plausible und realistische Biografie einer Person erzeugt. Berücksichtige "
            "soziokulturelle und altersbezogene Faktoren sowie typische Lebensereignisse. "
            "Formuliere die Biografie in 1-3 kurzen Sätzen. Antworte nur mit der Biografie."
        )
        return PromptSpec(
            attr_type=AttributeType.BIOGRAPHY,
            persona_id=str(persona.id),
            system_message=system_message,
            user_message=user_prompt,
        )
