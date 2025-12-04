from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TraitDto:
    """Minimal trait in the benchmark: id + adjective.

    case_template is optional and can be used later to add situational context.
    """

    id: str
    adjective: str
    case_template: Optional[str] = None
    category: Optional[str] = None
    valence: Optional[int] = None
    is_active: bool = True
