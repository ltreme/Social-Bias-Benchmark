from __future__ import annotations

from typing import Mapping


def describe_persona_de(ctx: Mapping[str, object]) -> str:
    """German persona rendering; mirrors your legacy order/labels."""
    p: list[str] = []

    name = ctx.get("name")
    if name:
        p.append(f"Name: {name}")

    if (age := ctx.get("Alter")) is not None:
        p.append(f"Alter: {age} Jahre")
    if gender := ctx.get("Geschlecht"):
        p.append(f"Geschlecht: {gender}")
    if edu := ctx.get("Bildung"):
        p.append(f"Bildungsstand: {edu}")
    if occ := ctx.get("Beruf"):
        p.append(f"Beruf: {occ}")
    if ms := ctx.get("Familienstand"):
        p.append(f"Familienstand: {ms}")
    if orig := ctx.get("Herkunft"):
        p.append(f"Herkunft: {orig}")
    if rel := ctx.get("Religion"):
        p.append(f"Religion: {rel}")
    if sex := ctx.get("Sexualität"):
        p.append(f"Sexualität: {sex}")

    if appearance := ctx.get("appearance"):
        p.append(f"Aussehen: {appearance}")
    if bio := ctx.get("biography"):
        p.append(f"Biografie: {bio}")

    return "\n".join(p)


def likert_5_de(adjective: str, reverse: bool = False) -> str:
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
