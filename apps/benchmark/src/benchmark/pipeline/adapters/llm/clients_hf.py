from __future__ import annotations

from ...ports import PromptSpec, LLMResult, LLMClient  # preprocessing pipeline
from ...ports_bench import BenchPromptSpec, LLMResult as BenchLLMResult, LLMClient as BenchLLMClient
from .base_hf import BaseHFClient


# --- Attr-Gen HF client --------------------------------------------------

class LlmClientHF(BaseHFClient[PromptSpec, LLMResult], LLMClient):
    def __init__(
        self,
        model_name_or_path: str,
        batch_size: int = 4,
        max_new_tokens_cap: int = 256,
        device_map: str | None = "auto",
        trust_remote_code: bool = False,
        use_bfloat16: bool = True,
    ):
        super().__init__(
            model_name_or_path=model_name_or_path,
            result_ctor=LLMResult,  # constructor signature: (spec, raw_text, gen_time_ms)
            batch_size=batch_size,
            max_new_tokens_cap=max_new_tokens_cap,
            device_map=device_map,
            trust_remote_code=trust_remote_code,
            use_bfloat16=use_bfloat16,
        )


# --- Benchmark HF client ------------------------------------------------------

class LlmClientHFBench(BaseHFClient[BenchPromptSpec, BenchLLMResult], BenchLLMClient):
    def __init__(
        self,
        model_name_or_path: str,
        batch_size: int = 4,
        max_new_tokens_cap: int = 256,
        device_map: str | None = "auto",
        trust_remote_code: bool = False,
        use_bfloat16: bool = True,
    ):
        super().__init__(
            model_name_or_path=model_name_or_path,
            result_ctor=BenchLLMResult,  # constructor signature: (spec, raw_text, gen_time_ms)
            batch_size=batch_size,
            max_new_tokens_cap=max_new_tokens_cap,
            device_map=device_map,
            trust_remote_code=trust_remote_code,
            use_bfloat16=use_bfloat16,
        )
