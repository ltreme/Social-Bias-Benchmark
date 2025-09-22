from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CaseDto:
    """Minimal case in the benchmark: id + adjective.

    case_template is optional and can be used later to add situational context.
    """
    id: str
    adjective: str
    case_template: Optional[str] = None
