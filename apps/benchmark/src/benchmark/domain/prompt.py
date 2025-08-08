from dataclasses import dataclass

from benchmark.domain.case import TaskDto
from benchmark.domain.persona import EnrichedPersonaDto


@dataclass(frozen=True)
class PromptDto:
    """
    Data Transfer Object for a prompt in the benchmark.
    Contains the prompt text and the associated question.
    """

    uuid: str
    text: str
    task: TaskDto
    persona: EnrichedPersonaDto
