from dataclasses import dataclass
from enum import Enum
from typing import Callable, Any, Optional
from transformers import StoppingCriteria

class AttributeType(str, Enum):
    NAME = "name"
    APPEARANCE = "appearance"
    BIOGRAPHY = "biography"

@dataclass(frozen=True)
class PromptSpec:
    """LLM-ready prompt container."""
    attr_type: AttributeType
    persona_id: str  # or int; whatever uniquely identifies the RawPersonaDto
    system_message: str
    user_message: str
