from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List, Protocol, NewType, Union, Literal

PersonaUUID = NewType("PersonaUUID", str)


# ---- Work + Prompt/Result specs (compatible with LLM adapters) ----
@dataclass(frozen=True, slots=True)
class BenchWorkItem:
    gen_id: int
    persona_uuid: PersonaUUID
    persona_context: dict  # enriched fields used for prompting
    question_uuid: str
    adjective: str
    question_template: str


@dataclass(frozen=True, slots=True)
class BenchPromptSpec:
    work: BenchWorkItem
    prompt_text: str
    max_new_tokens: int
    attempt: int
    model_name: str
    template_version: str
    benchmark_run_id: int


@dataclass(frozen=True, slots=True)
class LLMResult:
    spec: BenchPromptSpec
    raw_text: str
    gen_time_ms: int


@dataclass(frozen=True, slots=True)
class BenchAnswerDto:
    persona_uuid: PersonaUUID
    question_uuid: str
    model_name: str
    template_version: str
    benchmark_run_id: int
    attempt: int
    gen_time_ms: int
    answer_raw: str
    rating: int | None  # parsed Likert rating if available


# ---- Decisions ----
@dataclass(frozen=True, slots=True)
class OkDecision:
    kind: Literal["ok"]
    answers: List[BenchAnswerDto]


@dataclass(frozen=True, slots=True)
class RetryDecision:
    kind: Literal["retry"]
    reason: str
    retry_spec: BenchPromptSpec


@dataclass(frozen=True, slots=True)
class FailDecision:
    kind: Literal["fail"]
    reason: str
    raw_text_snippet: str


Decision = Union[OkDecision, RetryDecision, FailDecision]


# ---- Ports ----
class BenchPersonaRepo(Protocol):
    def iter_personas(self, gen_id: int) -> Iterable[BenchWorkItem]: ...


class BenchPromptFactory(Protocol):
    def prompts(self, items: Iterable[BenchWorkItem], *, model_name: str,
                template_version: str, attempt: int, benchmark_run_id: int) -> Iterable[BenchPromptSpec]: ...


class LLMClient(Protocol):
    def run_stream(self, specs: Iterable[BenchPromptSpec]) -> Iterable[LLMResult]: ...


class BenchPostProcessor(Protocol):
    def decide(self, res: LLMResult) -> Decision: ...


class BenchPersister(Protocol):
    def persist_results(self, rows: List[BenchAnswerDto]) -> None: ...
    # Reuse FailureDto from preprocess.ports in pipeline where needed.
    def persist_failure(self, fail) -> None: ...
