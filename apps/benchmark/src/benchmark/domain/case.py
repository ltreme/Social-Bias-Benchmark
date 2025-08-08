from dataclasses import dataclass


@dataclass(frozen=True)
class TaskDto:
    uuid: str
    adjective: str


@dataclass(frozen=True)
class QuestionDto(TaskDto):
    """
    Data Transfer Object for a question in the benchmark.
    Contains the question text and the expected property it addresses.
    """

    question_template: str


@dataclass(frozen=True)
class QuestionCaseDto(QuestionDto):
    """
    Combines question details with the case template for rendering.
    """

    case_template: str  # Template describing the scenario
