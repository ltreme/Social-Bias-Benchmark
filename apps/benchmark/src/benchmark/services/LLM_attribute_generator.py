import json

from benchmark.domain.persona import RawPersonaDto
from benchmark.llm.model import LLMModel


class LLMAttributeGenerator:
    def __init__(self, llm: LLMModel):
        self.llm = llm

    def gen_name(self, persona: RawPersonaDto) -> str:
        prompt = f"Generiere einen Namen für die folgenden Attribute:\n{json.dumps(persona.get_base_attributes())}\n"
        system_message = "Deine Aufgabe ist es, einen passenden Namen zu generieren. Antworte nur mit dem Namen."
        response = self.llm.call(prompt, system_message, 15)
        return response

    def gen_appearance(self, persona: RawPersonaDto) -> str:
        prompt = f"Generiere ein Aussehen für die folgenden Attribute:\n{json.dumps(persona.get_base_attributes())}\n"
        system_message = "Du bist ein Assistent, der aus strukturierten demografischen Daten eine möglichst plausible und realistische Beschreibung des äußeren Erscheinungsbilds einer Person erzeugt. Berücksichtige soziokulturelle und altersbezogene Faktoren sowie typische Merkmale, die sich aus Herkunft, Beruf, Bildung und Lebenssituation ergeben könnten. Formuliere die Beschreibung in 1–2 knappen Sätzen, beschreibend und konkret. Antworte nur mit der Beschreibung des Aussehens."
        response = self.llm.call(prompt, system_message, 50)
        return response

    def gen_biography(self, persona: RawPersonaDto) -> str:
        prompt = f"Generiere eine Biografie für die folgenden Attribute:\n{json.dumps(persona.get_base_attributes())}\n"
        system_message = "Du bist ein Assistent, der aus strukturierten demografischen Daten eine möglichst plausible und realistische Biografie einer Person erzeugt. Berücksichtige soziokulturelle und altersbezogene Faktoren sowie typische Lebensereignisse, die sich aus Herkunft, Beruf, Bildung und Lebenssituation ergeben könnten. Formuliere die Biografie in 3–5 Sätzen. Antworte nur mit der Biografie."
        response = self.llm.call(prompt, system_message, 100)
        return response
