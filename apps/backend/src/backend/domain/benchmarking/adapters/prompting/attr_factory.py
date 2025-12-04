from __future__ import annotations

from typing import Iterable

from ...ports import PromptFactory, PromptSpec, WorkItem
from .base import BasePromptFactory
from .utils_json import json_format_instruction_de, json_only_preamble_de

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
    def __init__(
        self, max_new_tokens: int = 160, *, system_preamble: str | None = None
    ):
        super().__init__(spec_ctor=PromptSpec, max_new_tokens=max_new_tokens)
        self._system_preamble = system_preamble

    # --- overrides -----------------------------------------------------------
    def system_preamble(self) -> str:
        if self._system_preamble:
            return self._system_preamble
        # Direkter, handlungsorientierter Prompt ohne negierte Anweisungen
        # (um zu verhindern, dass das Model die Instruktionen "reflektiert")
        return (
            "Du generierst fiktive Personenprofile basierend auf demografischen Attributen. "
            "Antworte immer mit genau einem JSON-Objekt in dieser Struktur:\n"
            "{\n"
            f'    "name": "Vollständiger Name, max. {NAME_MAX_CHARS} Zeichen",\n'
            f'    "appearance": "Aussehen in 1-2 Sätzen, max. {APPEARANCE_MAX_CHARS} Zeichen",\n'
            f'    "biography": "Kurzbiografie in 1-3 Sätzen, max. {BIO_MAX_CHARS} Zeichen"\n'
            "}\n\n"
            "Wichtig:\n"
            "- Wähle einen kulturell passenden Namen zur Herkunft und Religion.\n"
            "- Schreibe auf Deutsch.\n"
            "- Beginne deine Antwort direkt mit dem öffnenden { des JSON-Objekts."
        )

    def few_shots(self) -> str:
        return FEW_SHOT_DE

    def user_block(self, work: WorkItem) -> str:
        # Direkter Prompt ohne "Gib zurück"-Formulierungen
        persona = getattr(work, "persona_minimal", None)
        return f"Attribute: {persona}"
