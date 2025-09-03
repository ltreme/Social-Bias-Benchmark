from typing import Optional
from langchain_ollama import OllamaLLM as LangchainOllama
from benchmark.llm.abstract_llm import AbstractLLM

class OllamaLLM(AbstractLLM):
    """
    LLM wrapper for Ollama models.
    """

    def __init__(self, model_identifier: str):
        self._model_name = model_identifier
        self._llm = LangchainOllama(model=model_identifier)

    @property
    def model_name(self) -> str:
        return self._model_name

    def call(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        max_new_tokens: int = 2048,
    ) -> str:
        inputs = self._build_inputs(prompt, system_message)
        return self._generate(inputs, max_new_tokens)

    def batch_call(
        self,
        prompts: list[str],
        system_message: Optional[str] = None,
        max_new_tokens: int = 2048,
    ) -> list[str]:
        """
        Processes a batch of prompts in parallel.
        """
        if system_message:
            full_prompts = [f"{system_message}\n\n{prompt}" for prompt in prompts]
        else:
            full_prompts = prompts

        return self._llm.batch(full_prompts, num_predict=max_new_tokens)

    def _ensure_loaded(self) -> None:
        # Nothing to do here for Ollama as it's a service
        pass

    def _build_inputs(self, prompt: str, system_prompt: Optional[str]) -> str:
        if system_prompt:
            return f"{system_prompt}\n\n{prompt}"
        return prompt

    def _generate(self, inputs: str, max_new_tokens: int) -> str:
        return self._llm.invoke(inputs)
