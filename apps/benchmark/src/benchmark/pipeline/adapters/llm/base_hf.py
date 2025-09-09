from __future__ import annotations
from typing import TypeVar, Generic, Protocol, Iterable, Iterator, List
import time

from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# --- Protocols / Generics ----------------------------------------------------

class _SpecLike(Protocol):
    """Minimal surface expected from PromptSpec-like objects."""
    prompt_text: str
    max_new_tokens: int

class _ResultCtor(Protocol):
    """Callable to build an LLMResult-like object."""
    def __call__(self, *, spec, raw_text: str, gen_time_ms: int):
        ...

TSpec = TypeVar("TSpec", bound=_SpecLike)
TResult = TypeVar("TResult")

# --- Base class ---------------------------------------------------------------

class BaseHFClient(Generic[TSpec, TResult]):
    """
    Shared HF client for causal LMs.
    Handles: tokenizer/model setup, left padding, chat template, batching, generate, decode.
    Subclasses provide a result constructor via `result_ctor`.
    """

    def __init__(
        self,
        *,
        model_name_or_path: str,
        result_ctor: _ResultCtor,
        batch_size: int = 4,
        max_new_tokens_cap: int = 256,
        device_map: str | None = "auto",
        trust_remote_code: bool = False,
        use_bfloat16: bool = True,
    ):
        self.batch_size = batch_size
        self.max_new_tokens_cap = max_new_tokens_cap
        self.result_ctor = result_ctor

        # --- tokenizer -------------------------------------------------------
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name_or_path,
            trust_remote_code=trust_remote_code
        )

        # Ensure PAD exists and left padding for decoder-only
        if self.tokenizer.pad_token is None:
            if self.tokenizer.eos_token is not None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            else:
                self.tokenizer.add_special_tokens({"pad_token": "[PAD]"})
        self.tokenizer.padding_side = "left"

        # --- model -----------------------------------------------------------
        dtype = torch.bfloat16 if (use_bfloat16 and torch.cuda.is_available()) else None
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name_or_path,
            device_map=device_map,
            dtype=dtype,
            trust_remote_code=trust_remote_code,
        )

        # Resize embeddings if tokenizer grew (when adding PAD)
        if self.model.get_input_embeddings().num_embeddings < len(self.tokenizer):
            self.model.resize_token_embeddings(len(self.tokenizer))

        # Ensure pad_token_id exists on config
        if getattr(self.model.config, "pad_token_id", None) is None:
            self.model.config.pad_token_id = self.tokenizer.pad_token_id

        self.model_name_runtime = model_name_or_path

    # --- internals ------------------------------------------------------------

    def _format_texts(self, texts: List[str]) -> List[str]:
        """Apply chat template if available, else pass-through."""
        if hasattr(self.tokenizer, "apply_chat_template") and getattr(self.tokenizer, "chat_template", None):
            return [
                self.tokenizer.apply_chat_template(
                    [{"role": "user", "content": t}],
                    tokenize=False,
                    add_generation_prompt=True,
                )
                for t in texts
            ]
        return texts

    def _generate_batch(self, texts: List[str], max_new_tokens: int) -> List[str]:
        """Tokenize, generate, and decode only the generated continuation."""
        texts_fmt = self._format_texts(texts)
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

        # Input length per sample (works with left padding)
        input_lengths = tokens["attention_mask"].sum(dim=1)
        sequences = gen_out.sequences

        outs: List[str] = []
        for i in range(sequences.size(0)):
            start = int(input_lengths[i].item())
            gen_only = sequences[i, start:]
            outs.append(self.tokenizer.decode(gen_only, skip_special_tokens=True))
        return outs

    # --- public ---------------------------------------------------------------

    def run_stream(self, specs: Iterable[TSpec]) -> Iterable[TResult]:
        """Batch specs and yield TResult objects."""
        batch: List[TSpec] = []

        def flush() -> Iterator[TResult]:
            if not batch:
                return
            t0 = time.perf_counter()
            outs = self._generate_batch(
                [s.prompt_text for s in batch],
                max(s.max_new_tokens for s in batch),
            )
            dt = int((time.perf_counter() - t0) * 1000)
            for spec, raw in zip(batch, outs):
                yield self.result_ctor(spec=spec, raw_text=raw, gen_time_ms=dt)
            batch.clear()

        for s in specs:
            batch.append(s)
            if len(batch) >= self.batch_size:
                yield from flush()
        if batch:
            yield from flush()
