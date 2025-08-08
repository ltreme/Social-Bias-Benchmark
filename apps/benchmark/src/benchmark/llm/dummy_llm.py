from typing import Optional

from benchmark.llm.abstract_llm import AbstractLLM


class DummyLLM(AbstractLLM):
    """
    A dummy LLM implementation that simulates the behavior of a real LLM.
    This is useful for testing purposes without requiring an actual LLM.
    """

    def __init__(
        self,
        model_identifier: str,
        mixed_precision: str = "fp16",
        max_new_tokens: int = 30,
    ):
        self._model_name = model_identifier

    @property
    def model_name(self) -> str:
        # concrete implementation of the abstract property
        return self._model_name

    def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_new_tokens: int = 150,
    ) -> str:
        # Simulate LLM response
        print(f"Dummy LLM called with prompt: {prompt}")
        if system_prompt:
            print(f"System prompt: {system_prompt}")
        return f"dummy response"
