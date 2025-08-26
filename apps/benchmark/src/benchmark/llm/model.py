import os
import threading
from typing import Dict, Optional, Tuple

import torch
from transformers import (
    AutoConfig,
    AutoModelForCausalLM,
    AutoTokenizer,
    PreTrainedTokenizerBase,
)

from benchmark.llm.abstract_llm import AbstractLLM

# ---- Simple, process-wide cache (model + tokenizer) ----
_ModelKey = Tuple[str, str]  # (model_identifier, dtype_tag)
_MODEL_CACHE: Dict[_ModelKey, Tuple[AutoModelForCausalLM, PreTrainedTokenizerBase]] = {}
_MODEL_CACHE_LOCK = threading.Lock()


def _pick_device() -> torch.device:
    # Prefer CUDA, then Metal (MPS), then CPU
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _pick_dtype(mixed_precision: str) -> Optional[torch.dtype]:
    mp = mixed_precision.lower()
    if mp in {"bf16", "bfloat16"}:
        return torch.bfloat16
    if mp in {"fp16", "float16"}:
        return torch.float16
    return None  # full precision


class LLMModel(AbstractLLM):
    """
    Lean & robust LLM wrapper implementing AbstractLLM.

    Design choices:
    - Lazy, cached loading keyed by (model_id, dtype_tag).
    - No bitsandbytes/FA2/torch.compile magic here (Option 2 would add those, guarded).
    - Deterministic defaults (greedy), safe attention mask, left padding.
    - Chat template if available, else simple fallback prompt construction.
    """

    def __init__(self, model_identifier: str, mixed_precision: str = "bf16"):
        self._model_name = model_identifier
        self._mixed_precision = mixed_precision
        self._device = _pick_device()
        self._dtype = _pick_dtype(mixed_precision)
        # Lazy members
        self._model: Optional[AutoModelForCausalLM] = None
        self._tok: Optional[PreTrainedTokenizerBase] = None

    # --- AbstractLLM ---
    @property
    def model_name(self) -> str:
        return self._model_name

    # --- Internal: ensure loaded once, with cache ---
    def _ensure_loaded(self) -> None:
        if self._model is not None and self._tok is not None:
            return

        key: _ModelKey = (self._model_name, (self._dtype or torch.float32).__repr__())
        with _MODEL_CACHE_LOCK:
            if key in _MODEL_CACHE:
                self._model, self._tok = _MODEL_CACHE[key]
                return

            # Fresh load
            tok = AutoTokenizer.from_pretrained(
                self._model_name, trust_remote_code=True
            )
            if tok.pad_token is None:
                # Common safety: ensure pad token
                tok.pad_token = tok.eos_token
            tok.padding_side = "left"

            # Keep config simple & robust
            config = AutoConfig.from_pretrained(
                self._model_name, trust_remote_code=True
            )

            # Device-map: single device, avoid over-smart sharding for stability
            # If you want auto-shard later, we can add it back behind a flag.
            model = AutoModelForCausalLM.from_pretrained(
                self._model_name,
                config=config,
                torch_dtype=self._dtype,  # None => full precision
                trust_remote_code=True,
                device_map=None,  # load to host first, then move
            )

            # Move model to desired device (CUDA/MPS/CPU)
            model = model.to(self._device)
            model.eval()

            # Cache it
            _MODEL_CACHE[key] = (model, tok)
            self._model, self._tok = model, tok

    # --- Helpers ---
    def _build_inputs(self, prompt: str, system_prompt: Optional[str]) -> torch.Tensor:
        assert self._tok is not None
        # Try chat template if present
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": prompt})

        input_ids = None
        try:
            # Newer tokenizers with chat templates
            input_ids = self._tok.apply_chat_template(
                msgs, add_generation_prompt=True, return_tensors="pt"
            )
        except Exception:
            # Fallback: simple string concat
            text = (system_prompt + "\n\n" if system_prompt else "") + prompt
            input_ids = self._tok(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=getattr(self._tok, "model_max_length", 4096),
            )["input_ids"]
        return input_ids

    def _generate(self, input_ids: torch.Tensor, max_new_tokens: int) -> torch.Tensor:
        assert self._model is not None and self._tok is not None

        # Build attention mask safely
        if self._tok.pad_token_id is not None:
            attention_mask = (input_ids != self._tok.pad_token_id).long()
        else:
            attention_mask = torch.ones_like(input_ids)

        input_ids = input_ids.to(self._device)
        attention_mask = attention_mask.to(self._device)

        # Deterministic by default: sampling OFF. (Easier to debug.)
        # If you need sampling, we can expose it as env or method args later.
        with torch.inference_mode():
            out = self._model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=max_new_tokens,
                pad_token_id=self._tok.pad_token_id,
                eos_token_id=self._tok.eos_token_id,
                do_sample=False,
                use_cache=True,
                return_dict_in_generate=False,
            )
        return out

    # --- AbstractLLM ---
    def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_new_tokens: int = 150,
    ) -> str:
        self._ensure_loaded()
        assert self._tok is not None

        input_ids = self._build_inputs(prompt, system_prompt)
        outputs = self._generate(input_ids, max_new_tokens)

        # Slice off the prompt
        gen = outputs[0, input_ids.shape[1] :]
        text = self._tok.decode(gen, skip_special_tokens=True)
        return text.strip()
