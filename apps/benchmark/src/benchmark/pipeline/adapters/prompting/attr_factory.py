from __future__ import annotations
from typing import Iterable
from ...ports import PromptFactory, WorkItem, PromptSpec

from .base import BasePromptFactory
from .utils_json import json_only_preamble_de, json_format_instruction_de

# Centralized limits
NAME_MAX_CHARS = 40
APPEARANCE_MAX_CHARS = 220
BIO_MAX_CHARS = 420

# Few-shot kept from your original, can stay in this module or moved to a store.
FEW_SHOT_DE = """\
Beispiel 1:
Kontext:
{"Alter": 34, "Geschlecht": "weiblich", "Herkunft": "Deutschland", "Bildung": "Bachelor", "Beruf": "Produktmanagerin", "Familienstand": "verheiratet", "Religion": "keine", "Sexualität": "heterosexuell"}
Erwartete Ausgabe:
{"name":"Laura Neumann","appearance":"Mittellanges dunkelblondes Haar, dezente Brille; sachlicher Kleidungsstil.","biography":"Studierte Betriebswirtschaft, arbeitet seit einigen Jahren als Produktmanagerin in einem mittelständischen Unternehmen. Lebt in einer Stadtwohnung und treibt regelmäßig Sport."}

Beispiel 2:
Kontext:
{"Alter": 67, "Geschlecht": "männlich", "Herkunft": "Österreich", "Bildung": "Lehre", "Beruf": "Rentner", "Familienstand": "verheiratet", "Religion": "Christentum", "Sexualität": "heterosexuell"}
Erwartete Ausgabe:
{"name":"Franz Leitner","appearance":"Graues, kurzes Haar, gepflegter Schnurrbart; trägt oft eine schlichte Jacke.","biography":"Gelernter Handwerker, viele Jahre im Bau tätig. Verbringt den Ruhestand mit Wanderungen in der Umgebung und Zeit mit den Enkeln."}
"""

class AttributePromptFactory(BasePromptFactory[WorkItem, PromptSpec], PromptFactory):
    def __init__(self, max_new_tokens: int = 160, *, system_preamble: str | None = None):
        super().__init__(spec_ctor=PromptSpec, max_new_tokens=max_new_tokens)
        self._system_preamble = system_preamble

    # --- overrides -----------------------------------------------------------
    def system_preamble(self) -> str:
        if self._system_preamble:
            return self._system_preamble
        extra_rules = (
            "Gib genau diese Struktur zurück:\n"
            "{\n"
            f'    "name": "string, maximal {NAME_MAX_CHARS} Zeichen",\n'
            f'    "appearance": "string, maximal {APPEARANCE_MAX_CHARS} Zeichen, 1–2 knappe Sätze",\n'
            f'    "biography": "string, maximal {BIO_MAX_CHARS} Zeichen, 1–3 kurze Sätze"\n'
            "}\n\n"
            "Regeln:\n"
            "- Halte dich strikt an die übergebenen demografischen Attribute.\n"
            "- Wähle einen kulturell plausiblen Namen passend zu Herkunft, Alter und ggf. Religion.\n"
            "- Keine sensiblen oder stigmatisierenden Zuschreibungen; bleibe neutral-plausibel.\n"
            "- Verwende vollständiges, korrektes Deutsch (keine Platzhalter, kein Markdown, keine Backticks).\n"
            '- Keine weiteren Schlüssel außer "name", "appearance", "biography".'
        )
        return json_only_preamble_de(extra_rules)

    def few_shots(self) -> str:
        return FEW_SHOT_DE

    def user_block(self, work: WorkItem) -> str:
        # Minimal and robust instruction
        persona = getattr(work, "persona_minimal", None)
        return (
            "Kontext (Attribute der Person):\n"
            + str(persona)
            + "\n\n"
            "Gib die Ausgabe nur als einzelnes JSON-Objekt in einer Zeile zurück."
        )
