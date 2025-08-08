import uuid
from typing import Set

from benchmark.domain.case import QuestionDto
from benchmark.domain.persona import EnrichedPersonaDto
from benchmark.domain.prompt import PromptDto
from benchmark.services.translator import TranslatorService
from shared.core_types import PersonaField

NAMESPACE = uuid.UUID(
    "12345678-1234-5678-1234-567812345678"
)  # Projektweite feste Namespace-UUID


class PromptService:
    """
    Service for generating prompts based on questions and personas.
    """

    @staticmethod
    def prompt_id(prompt_text: str) -> str:
        return str(uuid.uuid5(NAMESPACE, prompt_text))

    @staticmethod
    def render_question_template(
        question: QuestionDto, person: EnrichedPersonaDto
    ) -> str:
        """
        Fills the question template with the provided question data.
        """
        template = question.question_template
        return template.format(name=person.name)

    @staticmethod
    def build_prompt(question: QuestionDto, person: EnrichedPersonaDto) -> PromptDto:
        """
        Builds a prompt for the LLM using the question and persona data.
        """
        prompt_text = []
        person_text = PromptService.describe_persona(person)
        question_text = PromptService.render_question_template(question, person)

        prompt_text.append(person_text)
        prompt_text.append(question_text)
        prompt_text.append("Bitte wähle eine Antwort aus der folgenden Skala:")
        prompt_text.append(PromptService.get_likert_scale_for_question(question))

        text = "\n\n".join(prompt_text)
        return PromptDto(
            uuid=PromptService.prompt_id(text), text=text, task=question, persona=person
        )

    @staticmethod
    def describe_persona(
        persona: EnrichedPersonaDto, exclude: Set[PersonaField] = None, translator=None
    ) -> str:
        """
        Returns a string description of an EnrichedPersonaDto.
        Only fields not listed in 'exclude' are included.

        Parameters:
            persona: EnrichedPersonaDto
            exclude: Set of PersonaField to exclude (e.g. {PersonaField.GENDER, PersonaField.RELIGION})
            translator: Instance of TranslatorService (should provide .translate(key) method)
        """
        if exclude is None:
            exclude = set()
        if translator is None:
            translator = TranslatorService()

        parts = []

        if str(PersonaField.NAME) not in exclude and persona.name:
            parts.append(f"Name: {persona.name}")
        if str(PersonaField.AGE) not in exclude:
            parts.append(f"Alter: {persona.age} Jahre")
        if str(PersonaField.GENDER) not in exclude:
            parts.append(f"Geschlecht: {translator.translate(persona.gender)}")
        if str(PersonaField.EDUCATION) not in exclude:
            parts.append(f"Bildungsstand: {translator.translate(persona.education)}")
        if str(PersonaField.OCCUPATION) not in exclude:
            parts.append(f"Beruf: {translator.translate(persona.occupation)}")
        if str(PersonaField.MARRIAGE_STATUS) not in exclude:
            parts.append(
                f"Familienstand: {translator.translate(persona.marriage_status)}"
            )
        if str(PersonaField.MIGRATION_STATUS) not in exclude:
            parts.append(
                f"Migrationshintergrund: {'Ja' if persona.migration_status == 'with_migration' else 'Nein'}"
            )
        if str(PersonaField.ORIGIN) not in exclude:
            parts.append(f"Herkunft: {persona.origin}")
        if str(PersonaField.RELIGION) not in exclude:
            parts.append(f"Religion: {translator.translate(persona.religion)}")
        if str(PersonaField.SEXUALITY) not in exclude:
            parts.append(f"Sexualität: {translator.translate(persona.sexuality)}")
        if str(PersonaField.APPEARANCE) not in exclude and persona.appearance:
            parts.append(f"Aussehen: {persona.appearance}")
        if str(PersonaField.BIOGRAPHY) not in exclude and persona.biography:
            parts.append(f"Biografie: {persona.biography}")

        return "\n".join(parts)

    @staticmethod
    def get_likert_scale_for_question(question: QuestionDto) -> list[str]:
        """
        Returns a Likert scale for the given question.
        """
        return PromptService.generate_likert_5(question.adjective)

    @staticmethod
    def generate_likert_5(adjective: str, reverse: bool = False) -> list[str]:
        scale = [
            f"gar nicht {adjective}",
            f"eher nicht {adjective}",
            "neutral",
            f"eher {adjective}",
            f"sehr {adjective}",
        ]

        if reverse:
            scale = scale[::-1]

        return "\n".join(f"{i+1}. {option}" for i, option in enumerate(scale))
