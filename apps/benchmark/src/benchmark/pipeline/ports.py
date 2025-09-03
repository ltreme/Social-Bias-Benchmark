# apps/benchmark/src/benchmark/pipeline/ports.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Protocol, NewType, Union, Literal

PersonaUUID = NewType("PersonaUUID", str)

@dataclass(frozen=True, slots=True)
class WorkItem:
    gen_id: int
    persona_uuid: PersonaUUID
    persona_minimal: dict  # only fields needed for prompting

@dataclass(frozen=True, slots=True)
class PromptSpec:
    work: WorkItem
    prompt_text: str
    max_new_tokens: int
    attempt: int
    model_name: str
    template_version: str

@dataclass(frozen=True, slots=True)
class LLMResult:
    spec: PromptSpec
    raw_text: str
    gen_time_ms: int     # we'll convert to seconds in the Persister

@dataclass(frozen=True, slots=True)
class AttributeDto:
    persona_uuid: PersonaUUID
    attribute_key: str
    value: str
    model_name: str
    gen_time_ms: int
    attempt: int

@dataclass(frozen=True, slots=True)
class FailureDto:
    persona_uuid: PersonaUUID
    model_name: str
    attempt: int
    error_kind: str
    raw_text_snippet: str
    prompt_snippet: str

class DecisionKind(Enum):
    OK = "ok"
    RETRY = "retry"
    FAIL = "fail"

@dataclass(frozen=True, slots=True)
class OkDecision:
    kind: Literal[DecisionKind.OK]
    attrs: List[AttributeDto]

@dataclass(frozen=True, slots=True)
class RetryDecision:
    kind: Literal[DecisionKind.RETRY]
    reason: str
    retry_spec: PromptSpec

@dataclass(frozen=True, slots=True)
class FailDecision:
    kind: Literal[DecisionKind.FAIL]
    reason: str
    raw_text_snippet: str

Decision = Union[OkDecision, RetryDecision, FailDecision]

class PersonaRepo(Protocol):
    def iter_personas(self, gen_id: int) -> Iterable[WorkItem]: ...

class PromptFactory(Protocol):
    def prompts(self, items: Iterable[WorkItem], *, model_name: str,
                template_version: str, attempt: int) -> Iterable[PromptSpec]: ...

class LLMClient(Protocol):
    def run_stream(self, specs: Iterable[PromptSpec]) -> Iterable[LLMResult]: ...

class PostProcessor(Protocol):
    def decide(self, res: LLMResult) -> Decision: ...

class Persister(Protocol):
    def persist_attributes(self, rows: List[AttributeDto]) -> None: ...
    def persist_failure(self, fail: FailureDto) -> None: ...
