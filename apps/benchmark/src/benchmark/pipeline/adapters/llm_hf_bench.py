from __future__ import annotations
from typing import Iterable, Iterator, List
import time

from ..ports_bench import BenchPromptSpec, LLMResult as BenchLLMResult, LLMClient


class LlmClientFakeBench(LLMClient):
    def __init__(self, batch_size: int = 4):
        self.batch_size = batch_size

    def run_stream(self, specs: Iterable[BenchPromptSpec]) -> Iterable[BenchLLMResult]:
        batch: List[BenchPromptSpec] = []

        def flush() -> Iterator[BenchLLMResult]:
            if not batch:
                return
            t0 = time.perf_counter()
            outs = ['{"rating": 3, "rationale": "ok"}' for _ in batch]
            dt = int((time.perf_counter() - t0) * 1000)
            for spec, raw in zip(batch, outs):
                yield BenchLLMResult(spec=spec, raw_text=raw, gen_time_ms=dt)
            batch.clear()

        for s in specs:
            batch.append(s)
            if len(batch) >= self.batch_size:
                yield from flush()
        yield from flush()


class LlmClientHFBench(LLMClient):
    def __init__(self, model_name_or_path: str, batch_size: int = 4, max_new_tokens_cap: int = 256,
                 device_map: str | None = "auto", trust_remote_code: bool = False, use_bfloat16: bool = True):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        self.batch_size = batch_size
        self.max_new_tokens_cap = max_new_tokens_cap

        self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, trust_remote_code=trust_remote_code)
        if self.tokenizer.pad_token is None:
            if self.tokenizer.eos_token is not None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            else:
                self.tokenizer.add_special_tokens({"pad_token": "[PAD]"})
        self.tokenizer.padding_side = "left"

        dtype = torch.bfloat16 if (use_bfloat16 and torch.cuda.is_available()) else None
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name_or_path,
            device_map=device_map,
            torch_dtype=dtype,
            trust_remote_code=trust_remote_code,
        )
        if self.model.get_input_embeddings().num_embeddings < len(self.tokenizer):
            self.model.resize_token_embeddings(len(self.tokenizer))
        if getattr(self.model.config, "pad_token_id", None) is None:
            self.model.config.pad_token_id = self.tokenizer.pad_token_id
        self.model_name_runtime = model_name_or_path

    def _generate_batch(self, texts: List[str], max_new_tokens: int) -> List[str]:
        # Chat-template aware formatting
        if hasattr(self.tokenizer, "apply_chat_template") and self.tokenizer.chat_template:
            texts_fmt = [
                self.tokenizer.apply_chat_template(
                    [{"role": "user", "content": t}],
                    tokenize=False,
                    add_generation_prompt=True,
                )
                for t in texts
            ]
        else:
            texts_fmt = texts

        tok_kwargs = dict(return_tensors="pt", padding=True, truncation=False)
        tokens = self.tokenizer(texts_fmt, **tok_kwargs)
        tokens = {k: v.to(self.model.device) for k, v in tokens.items()}

        gen_out = self.model.generate(
            **tokens,
            max_new_tokens=min(max_new_tokens, self.max_new_tokens_cap),
            do_sample=False,
            pad_token_id=self.tokenizer.pad_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
            return_dict_in_generate=True,
            output_scores=False,
        )

        input_lengths = tokens["attention_mask"].sum(dim=1)
        sequences = gen_out.sequences

        outs: List[str] = []
        for i in range(sequences.size(0)):
            start = int(input_lengths[i].item())
            gen_only = sequences[i, start:]
            outs.append(self.tokenizer.decode(gen_only, skip_special_tokens=True))
        return outs

    def run_stream(self, specs: Iterable[BenchPromptSpec]) -> Iterable[BenchLLMResult]:
        batch: List[BenchPromptSpec] = []

        def flush() -> Iterator[BenchLLMResult]:
            if not batch:
                return
            t0 = time.perf_counter()
            outs = self._generate_batch([s.prompt_text for s in batch], max(b.max_new_tokens for b in batch))
            dt = int((time.perf_counter() - t0) * 1000)
            for spec, raw in zip(batch, outs):
                yield BenchLLMResult(spec=spec, raw_text=raw, gen_time_ms=dt)
            batch.clear()

        for s in specs:
            batch.append(s)
            if len(batch) >= self.batch_size:
                yield from flush()
        yield from flush()

