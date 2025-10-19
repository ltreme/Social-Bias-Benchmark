# apps/benchmark/src/benchmark/pipeline/adapters/llm/fake_clients.py
from __future__ import annotations
from typing import Iterable, Iterator, List
import time

from ...ports import PromptSpec, LLMResult, LLMClient
from ...ports_bench import BenchPromptSpec, LLMResult as BenchLLMResult, LLMClient as BenchLLMClient


class _BaseFake:
    """Shared batching logic for fake clients."""
    def __init__(self, batch_size: int = 4):
        self.batch_size = batch_size

    def _run_fake(self, specs, payload: str, result_ctor):
        batch: List = []

        def flush() -> Iterator:
            if not batch:
                return
            t0 = time.perf_counter()
            outs = [payload for _ in batch]
            dt = int((time.perf_counter() - t0) * 1000)
            for spec, raw in zip(batch, outs):
                yield result_ctor(spec=spec, raw_text=raw, gen_time_ms=dt)
            batch.clear()

        for s in specs:
            batch.append(s)
            if len(batch) >= self.batch_size:
                yield from flush()
        if batch:
            yield from flush()


class LlmClientFake(_BaseFake, LLMClient):
    """Preprocessing: emits attribute JSON."""
    def run_stream(self, specs: Iterable[PromptSpec]):
        payload = '{"name":"Max","appearance":"short","biography":"short"}'
        yield from self._run_fake(specs, payload, LLMResult)


class LlmClientFakeBench(_BaseFake, BenchLLMClient):
    """Benchmark: emits likert JSON."""
    def run_stream(self, specs: Iterable[BenchPromptSpec]):
        payload = '{"rating": 3, "rationale": "ok"}'
        yield from self._run_fake(specs, payload, BenchLLMResult)
