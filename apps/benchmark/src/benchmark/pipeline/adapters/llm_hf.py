# apps/benchmark/src/benchmark/pipeline/adapters/llm_hf.py
from __future__ import annotations
from typing import Iterable, Iterator, List
import time
from ..ports import PromptSpec, LLMResult, LLMClient
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

class LlmClientFake(LLMClient):
    def __init__(self, batch_size: int = 4):
        self.batch_size = batch_size

    def run_stream(self, specs: Iterable[PromptSpec]) -> Iterable[LLMResult]:
        batch: List[PromptSpec] = []

        def flush() -> Iterator[LLMResult]:
            if not batch:
                return
            t0 = time.perf_counter()
            outs = ['{"name":"Max","appearance":"short","biography":"short"}' for _ in batch]
            dt = int((time.perf_counter() - t0) * 1000)
            for spec, raw in zip(batch, outs):
                yield LLMResult(spec=spec, raw_text=raw, gen_time_ms=dt)
            batch.clear()

        for s in specs:
            batch.append(s)
            if len(batch) >= self.batch_size:
                yield from flush()
        yield from flush()

# Optional: HF-Client (nur wenn du transformers einsetzen willst)
class LlmClientHF(LLMClient):
    def __init__(self, model_name_or_path: str, batch_size: int = 4, max_new_tokens_cap: int = 256,
            device_map: str | None = "auto", trust_remote_code: bool = False, use_bfloat16: bool = True):
        

        self.batch_size = batch_size
        self.max_new_tokens_cap = max_new_tokens_cap

        self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, trust_remote_code=trust_remote_code)

        # --- PAD-Fix ---
        if self.tokenizer.pad_token is None:
            if self.tokenizer.eos_token is not None:
                # Variante A: eos als pad
                self.tokenizer.pad_token = self.tokenizer.eos_token
            else:
                # Variante B: echten PAD hinzufügen
                self.tokenizer.add_special_tokens({"pad_token": "[PAD]"})
        # Für Decoder-Only-Modelle empfohlen:
        self.tokenizer.padding_side = "left"

        dtype = torch.bfloat16 if (use_bfloat16 and torch.cuda.is_available()) else None
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name_or_path,
            device_map=device_map,
            torch_dtype=dtype,
            trust_remote_code=trust_remote_code,
        )

        # Falls wir neue Tokens ergänzt haben (Variante B), Embeddings anpassen:
        if self.model.get_input_embeddings().num_embeddings < len(self.tokenizer):
            self.model.resize_token_embeddings(len(self.tokenizer))

        # pad_token_id im Modell setzen (wichtig für generate/padding)
        if getattr(self.model.config, "pad_token_id", None) is None:
            self.model.config.pad_token_id = self.tokenizer.pad_token_id

        self.model_name_runtime = model_name_or_path

    def _generate_batch(self, texts: List[str], max_new_tokens: int) -> List[str]:
        import torch

        # 1) Falls Chat-Template vorhanden: Eingaben als Chat verpacken + Generation-Prompt anhängen
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
            # Fallback: plain text (geht, aber schlechter für Chat-Checkpoints)
            texts_fmt = texts

        # 2) Tokenisieren mit Left-Padding (decoder-only) und ohne „heimliches“ truncation
        tok_kwargs = dict(return_tensors="pt", padding=True, truncation=False)
        tokens = self.tokenizer(texts_fmt, **tok_kwargs)
        tokens = {k: v.to(self.model.device) for k, v in tokens.items()}

        # 3) Generieren; Rückgabe als Dict, damit wir Input-Längen kennen
        gen_out = self.model.generate(
            **tokens,
            max_new_tokens=min(max_new_tokens, self.max_new_tokens_cap),
            do_sample=False,
            pad_token_id=self.tokenizer.pad_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
            return_dict_in_generate=True,
            output_scores=False,
        )

        # 4) Nur den neu generierten Teil je Sample decodieren (nicht den Prompt!)
        #    Input-Länge = Summe der Attention-Maske je Zeile (bei Left-Padding korrekt)
        input_lengths = tokens["attention_mask"].sum(dim=1)  # shape: [bs]
        sequences = gen_out.sequences  # shape: [bs, seq_len_total]

        outs = []
        for i in range(sequences.size(0)):
            start = int(input_lengths[i].item())
            gen_only = sequences[i, start:]  # nur Fortsetzung
            outs.append(self.tokenizer.decode(gen_only, skip_special_tokens=True))
        return outs

    def run_stream(self, specs: Iterable[PromptSpec]) -> Iterable[LLMResult]:
        batch: List[PromptSpec] = []

        def flush() -> Iterator[LLMResult]:
            if not batch:
                return
            t0 = time.perf_counter()
            outs = self._generate_batch([s.prompt_text for s in batch], max(b.max_new_tokens for b in batch))
            dt = int((time.perf_counter() - t0) * 1000)
            for spec, raw in zip(batch, outs):
                yield LLMResult(spec=spec, raw_text=raw, gen_time_ms=dt)
            batch.clear()

        for s in specs:
            batch.append(s)
            if len(batch) >= self.batch_size:
                yield from flush()
        yield from flush()
