import json
import os
import re

from benchmark.domain.persona import RawPersonaDto
from benchmark.llm.model import LLMModel
from benchmark.services.language_service import persona_to_dict


class LLMAttributeGenerator:
    """Erzeugt freitextliche Persona-Attribute (Name, Appearance, Biography) via LLM.

    Beinhaltet Heuristiken um Ketten von Gedanken / Reasoning-Anteile (z.B. <think>-Blöcke
    oder Analyse-Zeilen) zu entfernen, damit nur die finale Antwort gespeichert wird.
    Längen- und Token-Limits sind über Environment-Variablen anpassbar, damit
    "Thinking"-Modelle mehr Raum erhalten können.
    """

    def __init__(self, llm: LLMModel):
        self.llm = llm

        def _int_env(name: str, default: int) -> int:
            try:
                return max(int(os.getenv(name, str(default))), 0)
            except ValueError:
                return default

        # Zeichen-Limits nach Cleaning
        self.appearance_max_chars = _int_env("APPEARANCE_MAX_CHARS", 800)
        self.bio_max_chars = _int_env("BIO_MAX_CHARS", 2000)
        # Token Budgets
        self.tokens_name = _int_env("NAME_MAX_NEW_TOKENS", 25)
        self.tokens_appearance = _int_env("APPEARANCE_MAX_NEW_TOKENS", 80)
        self.tokens_biography = _int_env("BIO_MAX_NEW_TOKENS", 220)

    # -------------------- Cleaning Helpers --------------------
    def _strip_thinking(self, text: str) -> str:
        if not text:
            return text
        # Entferne <think> ... </think>
        text = re.sub(r"(?is)<think>.*?</think>", "", text)
        filtered: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            low = line.lower()
            if low.startswith(("analysis", "reason", "thought", "we need")):
                continue
            attr_hits = sum(
                k in low
                for k in (
                    "age",
                    "gender",
                    "occupation",
                    "education",
                    "migration",
                    "origin",
                    "religion",
                    "sexuality",
                )
            )
            if attr_hits >= 3 and len(low) > 40:
                # Prompt Echo / Attributliste -> verwerfen
                continue
            filtered.append(line)
        if filtered:
            text = "\n".join(filtered)
        # Überflüssige Quotes entfernen
        text = text.strip().strip("'\"`“”„‚’")
        return text.strip()

    def _cleanup_name(self, text: str) -> str:
        text = self._strip_thinking(text)
        first = re.split(r"[\n,:;]|\\|/", text, 1)[0]
        first = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿÄÖÜäöüß '\-]", "", first)
        first = re.sub(r"\s+", " ", first).strip()
        if len(first.split()) > 4:
            first = " ".join(first.split()[:4])
        return first

    def _cleanup_text(self, text: str, max_len: int | None = None) -> str:
        text = self._strip_thinking(text)
        text = re.sub(r"(?is)antworte nur.*$", "", text).strip()
        if max_len and len(text) > max_len:
            text = text[:max_len].rsplit(" ", 1)[0].rstrip(".,;: ") + "..."
        return text.strip()

    # -------------------- Public API --------------------
    def gen_name(self, persona: RawPersonaDto) -> str:
        prompt = (
            "Generiere einen Namen für die folgenden Attribute:\n"
            + json.dumps(persona_to_dict(persona))
            + "\n"
        )
        system_message = "Deine Aufgabe ist es, einen passenden Namen zu generieren. Antworte nur mit dem Namen."
        response = self.llm.call(prompt, system_message, self.tokens_name)
        return self._cleanup_name(response)

    def gen_appearance(self, persona: RawPersonaDto) -> str:
        prompt = (
            "Generiere ein Aussehen für die folgenden Attribute:\n"
            + json.dumps(persona_to_dict(persona))
            + "\n"
        )
        system_message = (
            "Du bist ein Assistent, der aus strukturierten demografischen Daten eine möglichst plausible und realistische Beschreibung des äußeren Erscheinungsbilds einer Person erzeugt. "
            "Berücksichtige soziokulturelle und altersbezogene Faktoren sowie typische Merkmale, die sich aus Herkunft, Beruf, Bildung und Lebenssituation ergeben könnten. "
            "Formuliere die Beschreibung in 1–2 knappen Sätzen, beschreibend und konkret. Antworte nur mit der Beschreibung des Aussehens."
        )
        response = self.llm.call(prompt, system_message, self.tokens_appearance)
        return self._cleanup_text(response, max_len=self.appearance_max_chars)

    def gen_biography(self, persona: RawPersonaDto) -> str:
        prompt = (
            "Generiere eine Biografie für die folgenden Attribute:\n"
            + json.dumps(persona_to_dict(persona))
            + "\n"
        )
        system_message = (
            "Du bist ein Assistent, der aus strukturierten demografischen Daten eine möglichst plausible und realistische Biografie einer Person erzeugt. "
            "Berücksichtige soziokulturelle und altersbezogene Faktoren sowie typische Lebensereignisse, die sich aus Herkunft, Beruf, Bildung und Lebenssituation ergeben könnten. "
            "Formuliere die Biografie in 3–5 Sätzen. Antworte nur mit der Biografie."
        )
        response = self.llm.call(prompt, system_message, self.tokens_biography)
        return self._cleanup_text(response, max_len=self.bio_max_chars)
