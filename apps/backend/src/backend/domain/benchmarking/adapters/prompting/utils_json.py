# comments in English
from __future__ import annotations


def json_only_preamble_de(extra_rules: str = "") -> str:
    """Strict German preamble enforcing single JSON object."""
    base = (
        "Du bist ein strenger JSON-Generator. Antworte ausschließlich mit einem einzigen "
        "gültigen JSON-Objekt, ohne Prosa, ohne Erklärungen, ohne Markdown. Sprache: Deutsch."
    )
    if extra_rules:
        base += "\n" + extra_rules.strip()
    return base


def json_format_instruction_de(fmt_block: str) -> str:
    """Append a short 'Format:' reminder."""
    return "Format:\n" + fmt_block.strip()
