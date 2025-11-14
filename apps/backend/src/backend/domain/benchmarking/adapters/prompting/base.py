from __future__ import annotations

from typing import Callable, Generic, Iterable, Protocol, TypeVar


# Minimal protocols to decouple from ports modules.
class _WorkLike(Protocol):
    # For Attribute: persona_minimal; for Likert: persona_context, case_template, adjective
    pass


class _SpecCtor(Protocol):
    def __call__(
        self,
        *,
        work,
        prompt_text: str,
        max_new_tokens: int,
        attempt: int,
        model_name: str,
        template_version: str,
    ): ...


W = TypeVar("W", bound=_WorkLike)
S = TypeVar("S")  # PromptSpec-like


class BasePromptFactory(Generic[W, S]):
    """Shared prompting helpers: preamble + few-shots + user block + Spec construction."""

    def __init__(self, *, spec_ctor: _SpecCtor, max_new_tokens: int = 160):
        self.spec_ctor: Callable[..., S] = spec_ctor
        self.max_new_tokens = max_new_tokens

    # --- overridables --------------------------------------------------------
    def system_preamble(self) -> str:
        """Return the system preamble (language, JSON policy, etc.)."""
        return ""

    def few_shots(self) -> str:
        """Optional few-shot block appended after preamble."""
        return ""

    def user_block(self, work: W) -> str:
        """Compose the user-visible part of the prompt from work item."""
        raise NotImplementedError

    # --- public --------------------------------------------------------------
    def prompts(
        self,
        items: Iterable[W],
        *,
        model_name: str,
        template_version: str,
        attempt: int,
    ) -> Iterable[S]:
        pre = self.system_preamble()
        shots = self.few_shots()
        head = (pre + ("\n" + shots if shots else "")).strip()

        for w in items:
            body = self.user_block(w).strip()
            prompt = (head + "\n\n" + body).strip() if head else body
            yield self.spec_ctor(
                work=w,
                prompt_text=prompt,
                max_new_tokens=self.max_new_tokens,
                attempt=attempt,
                model_name=model_name,
                template_version=template_version,
            )
