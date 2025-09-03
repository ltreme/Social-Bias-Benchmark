# apps/benchmark/src/benchmark/pipeline/adapters/prompt_factory_attr.py
from __future__ import annotations
from typing import Iterable
from ..ports import PromptFactory, WorkItem, PromptSpec

# Konfigurierbare Limits (bewusst knapp halten, damit kleine Modelle sicher ins Budget passen)
NAME_MAX_CHARS = 40
APPEARANCE_MAX_CHARS = 220
BIO_MAX_CHARS = 420

SYSTEM_PREAMBLE_DE = f"""\
Du bist ein strenger JSON-Generator. Antworte **ausschließlich** mit einem einzigen gültigen JSON-Objekt, ohne Prosa, ohne Erklärungen, ohne Markdown.
Sprache: Deutsch.

Gib **genau** diese Struktur zurück:
{{
    "name": "string, maximal {NAME_MAX_CHARS} Zeichen",
    "appearance": "string, maximal {APPEARANCE_MAX_CHARS} Zeichen, 1–2 knappe Sätze",
    "biography": "string, maximal {BIO_MAX_CHARS} Zeichen, 1–3 kurze Sätze"
}}

Regeln:
- Halte dich strikt an die übergebenen demografischen Attribute.
- Wähle einen kulturell plausiblen Namen passend zu Herkunft, Alter und ggf. Religion.
- Keine sensiblen oder stigmatisierenden Zuschreibungen; bleibe neutral-plausibel.
- Verwende vollständiges, korrektes Deutsch (keine Platzhalter, kein Markdown, keine Backticks).
- Keine weiteren Schlüssel außer "name", "appearance", "biography".
"""

# Zwei sehr kleine Few-Shot-Beispiele erhöhen Format-Treue auch bei kleineren Modellen.
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

def _build_user_block(persona_minimal: dict) -> str:
    # Minimaler, robuster deutschsprachiger Auftrag
    return (
        "Kontext (Attribute der Person):\n"
        + str(persona_minimal)
        + "\n\n"
        "Gib die Ausgabe **nur** als einzelnes JSON-Objekt in einer Zeile zurück.\n"
    )

class AttributePromptFactory(PromptFactory):
    def __init__(self, system_preamble: str | None = None, max_new_tokens: int = 160):
        self.system_preamble = system_preamble or (SYSTEM_PREAMBLE_DE + "\n" + FEW_SHOT_DE)
        self.max_new_tokens = max_new_tokens

    def prompts(self, items: Iterable[WorkItem], *, model_name: str,
                template_version: str, attempt: int) -> Iterable[PromptSpec]:
        # Ein Prompt pro Persona; enthält System-Preamble + Few-Shot + konkreten Kontext
        for w in items:
            user = _build_user_block(w.persona_minimal)
            prompt = self.system_preamble + "\n" + user
            yield PromptSpec(
                work=w,
                prompt_text=prompt,
                max_new_tokens=self.max_new_tokens,
                attempt=attempt,
                model_name=model_name,
                template_version=template_version,
            )
