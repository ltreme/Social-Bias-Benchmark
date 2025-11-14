from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Literal, NewType, Protocol, Union

PersonaUUID = NewType("PersonaUUID", str)


# ---- Work + Prompt/Result specs (compatible with LLM adapters) ----
@dataclass(frozen=True, slots=True)
class BenchWorkItem:
    dataset_id: int
    persona_uuid: PersonaUUID
    persona_context: dict  # enriched fields used for prompting
    case_id: str
    adjective: str
    case_template: str | None
    # Likert scale order flag at item level (False=in-order, True=reversed)
    scale_reversed: bool = False


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
    case_id: str
    model_name: str
    template_version: str
    benchmark_run_id: int
    attempt: int
    gen_time_ms: int
    answer_raw: str
    rating: int | None  # parsed Likert rating if available
    scale_reversed: bool = False


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
    def iter_personas(self, dataset_id: int | None) -> Iterable[BenchWorkItem]: ...
    def count(self, dataset_id: int | None) -> int: ...


class BenchPromptFactory(Protocol):
    def prompts(
        self,
        items: Iterable[BenchWorkItem],
        *,
        model_name: str,
        template_version: str,
        attempt: int,
        benchmark_run_id: int,
    ) -> Iterable[BenchPromptSpec]: ...


class LLMClient(Protocol):
    def run_stream(self, specs: Iterable[BenchPromptSpec]) -> Iterable[LLMResult]: ...


class BenchPostProcessor(Protocol):
    def decide(self, res: LLMResult) -> Decision: ...


class BenchPersister(Protocol):
    def persist_results(self, rows: List[BenchAnswerDto]) -> None: ...

    # Reuse FailureDto from preprocess.ports in pipeline where needed.
    def persist_failure(self, fail) -> None: ...
