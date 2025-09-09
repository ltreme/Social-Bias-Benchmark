from typing import Optional
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from benchmark.llm.abstract_llm import AbstractLLM

class HuggingFaceLLM(AbstractLLM):
    """
    LLM wrapper for Hugging Face Transformer models.
    """

    def __init__(self, model_identifier: str):
        self._model_name = model_identifier
        self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
        self._model = AutoModelForCausalLM.from_pretrained(
            self._model_name,
            device_map="auto",
            dtype=torch.bfloat16,
        )
        self._pipeline = pipeline(
            "text-generation",
            model=self._model,
            tokenizer=self._tokenizer,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )


    @property
    def model_name(self) -> str:
        return self._model_name

    def call(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        max_new_tokens: int = 2048,
    ) -> str:
        messages = self._build_inputs(prompt, system_message)
        prompt_str = self._tokenizer.apply_chat_template(messages, tokenize=False)
        outputs = self._pipeline(
            prompt_str,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.95,
        )
        return outputs[0]["generated_text"]

    def batch_call(
        self,
        prompts: list[str],
        system_message: Optional[str] = None,
        max_new_tokens: int = 2048,
    ) -> list[str]:
        """
        Processes a batch of prompts in parallel.
        """
        full_prompts = []
        for prompt in prompts:
            messages = self._build_inputs(prompt, system_message)
            # The pipeline expects the messages in a specific format, 
            # so we apply the template and create a single string.
            full_prompts.append(self._tokenizer.apply_chat_template(messages, tokenize=False))

        outputs = self._pipeline(
            full_prompts,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.95,
        )
        
        # The pipeline returns a list of lists of dictionaries.
        return [output[0]["generated_text"] for output in outputs]


    def _ensure_loaded(self) -> None:
        # Model is loaded in __init__
        pass

    def _build_inputs(self, prompt: str, system_prompt: Optional[str]) -> list[dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages
