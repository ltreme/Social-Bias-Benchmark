from __future__ import annotations

from typing import Mapping


def describe_persona_de(ctx: Mapping[str, object]) -> str:
    """German persona rendering; mirrors your legacy order/labels."""
    p: list[str] = []

    name = ctx.get("name")
    if name:
        p.append(f"Name: {name}")

    # Support both 'age' and 'Alter' keys for flexibility
    age = ctx.get("Alter") or ctx.get("age")
    if age is not None:
        p.append(f"Alter: {age} Jahre")
    # Support both 'gender' and 'Geschlecht' keys
    gender = ctx.get("Geschlecht") or ctx.get("gender")
    if gender:
        p.append(f"Geschlecht: {gender}")
    # Support both 'education' and 'Bildung' keys
    edu = ctx.get("Bildung") or ctx.get("education")
    if edu:
        p.append(f"Bildungsstand: {edu}")
    # Support both 'occupation' and 'Beruf' keys
    occ = ctx.get("Beruf") or ctx.get("occupation")
    if occ:
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
    """Generate a 5-point Likert scale in German.

    For order-consistency analysis, the "reversed" scale should present options
    in reversed ORDER but with NORMAL numbering (1-5), so that:
    - Normal:   1="gar nicht X", 5="sehr X"
    - Reversed: 1="sehr X", 5="gar nicht X"

    This way, a consistent model should give: rating_in + rating_rev = 6
    (e.g., "sehr X" = 5 on normal, = 1 on reversed → 5+1=6)
    """
    scale = [
        f"gar nicht {adjective}",
        f"eher nicht {adjective}",
        "neutral",
        f"eher {adjective}",
        f"sehr {adjective}",
    ]
    if reverse:
        scale = list(reversed(scale))
    # Always use 1-5 numbering
    return "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(scale))
