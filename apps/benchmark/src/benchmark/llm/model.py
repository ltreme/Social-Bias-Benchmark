import logging
import os
import time
import warnings
from typing import Optional

import torch
import transformers
from huggingface_hub import login
from transformers import (
    AutoConfig,
    AutoModelForCausalLM,
    AutoTokenizer,
    PreTrainedTokenizerFast,
)

from benchmark.llm.abstract_llm import AbstractLLM

# Configure basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Suppress some common warnings that might clutter output
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")


class LLMModel(AbstractLLM):
    def __init__(
        self,
        model_identifier: str,
        mixed_precision: str = "fp16",
        load_in_4bit: bool = False,
        load_in_8bit: bool = False,
        no_quantization: bool = False,
    ):
        """
        Initialize the LLM model.

        Args:
            model_identifier: The identifier of the model on Hugging Face.
            mixed_precision: The mixed precision to use (e.g., "fp16", "bf16").
        """
        # Authenticate with HuggingFace if token is available
        hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
        if hf_token:
            try:
                login(token=hf_token)
                logging.info("✅ HuggingFace authentication successful")
            except Exception as e:
                logging.warning(f"⚠️ HuggingFace authentication failed: {e}")
        else:
            logging.warning(
                "⚠️ No HuggingFace token found. Gated models may not be accessible."
            )

        self.mixed_precision = mixed_precision
        self._model_name = model_identifier
        self.tokenizer: Optional[AutoTokenizer] = None
        self.model: Optional[AutoModelForCausalLM] = None
        self.hf_token = hf_token  # für spätere Fallback-Ladevorgänge

        # Quantisierungs-Präferenzen
        self.load_in_4bit = load_in_4bit
        self.load_in_8bit = load_in_8bit
        if os.getenv("LLM_DISABLE_QUANTIZATION", "").lower() in {"1", "true", "yes"}:
            no_quantization = True
        self.no_quantization = no_quantization

        if self.load_in_4bit and self.load_in_8bit:
            logging.warning(
                "Beide Flags load_in_4bit und load_in_8bit gesetzt – verwende 4bit und ignoriere 8bit."
            )
            self.load_in_8bit = False

        self._load_model()

    @property
    def model_name(self) -> str:
        # concrete implementation of the abstract property
        return self._model_name

    def _build_quant_config(self):
        """Erstellt optional eine BitsAndBytesConfig, falls kompatibel. Gibt None zurück, wenn deaktiviert oder inkompatibel."""
        if self.no_quantization or not (self.load_in_4bit or self.load_in_8bit):
            if self.no_quantization:
                logging.info(
                    "Quantisierung deaktiviert (Flag oder ENV). Lade in Vollpräzision / gemischter Präzision."
                )
            return None
        try:
            from transformers import BitsAndBytesConfig  # lokal importieren (optional)
        except Exception:
            logging.warning("bitsandbytes nicht installiert – lade ohne Quantisierung.")
            return None
        # API-Kompatibilität prüfen
        if not hasattr(BitsAndBytesConfig, "get_loading_attributes"):
            logging.warning(
                "BitsAndBytesConfig veraltet (kein get_loading_attributes). Aktualisiere mit: pip install -U bitsandbytes accelerate. Lade ohne Quantisierung."
            )
            return None
        if self.load_in_4bit:
            logging.info(
                "Aktiviere 4-bit Quantisierung (nf4, double quant, bfloat16 compute)."
            )
            return BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
        if self.load_in_8bit:
            logging.info("Aktiviere 8-bit Quantisierung.")
            return BitsAndBytesConfig(load_in_8bit=True)
        return None

    def _load_model(self):
        logging.info(f"Starting to load model: {self.model_name}")
        logging.info(f"Available GPUs: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            logging.info(f"GPU {i}: {torch.cuda.get_device_name(i)}")

        start_time = time.time()
        # Config laden (immer mit trust_remote_code True für neue Modellfamilien wie Mistral 3.x)
        config = AutoConfig.from_pretrained(
            self.model_name,
            trust_remote_code=True,
            token=self.hf_token,
        )

        # Diagnose: Log relevante Versionen einmalig
        try:
            logging.info(
                f"transformers=={getattr(transformers, '__version__', 'unknown')} | bitsandbytes=="
                f"{__import__('importlib').import_module('bitsandbytes').__version__ if __import__('importlib').util.find_spec('bitsandbytes') else 'n/a'}"
            )
        except Exception:
            pass

        # Manche Configs enthalten bereits quantization_config (z.B. aus Hub), die ggf. mit neuer API kollidiert.
        existing_qc = getattr(config, "quantization_config", None)
        if existing_qc is not None and not hasattr(
            existing_qc, "get_loading_attributes"
        ):
            logging.warning(
                "Entferne veraltete config.quantization_config (fehlende get_loading_attributes). "
                "Upgrade von transformers oder erneutes Speichern des Modells empfohlen."
            )
            try:
                config.quantization_config = None
            except Exception:
                pass
            # Hard removal fallback
            try:
                if "quantization_config" in config.__dict__:
                    del config.__dict__["quantization_config"]
            except Exception:
                pass

        # Monkey-Patch BitsAndBytesConfig falls die neue API fehlt (verhindert Crash im merge_quantization_configs)
        try:
            from transformers import BitsAndBytesConfig as _BB

            if not hasattr(_BB, "get_loading_attributes"):
                logging.warning(
                    "Patche BitsAndBytesConfig mit Dummy get_loading_attributes(), da Version inkonsistent ist."
                )

                def _dummy_get_loading_attributes(self):  # type: ignore
                    return {}

                _BB.get_loading_attributes = _dummy_get_loading_attributes  # type: ignore
        except Exception:
            pass

        # Tokenizer robust laden – ältere transformers-Versionen kennen evtl. Mistral3Config nicht im Mapping
        tok_kwargs = dict(trust_remote_code=True)
        if self.hf_token:
            tok_kwargs["token"] = self.hf_token

        tokenizer_loaded = False
        last_tokenizer_error: Optional[Exception] = None

        # Schritt 1: AutoTokenizer (fast)
        if not tokenizer_loaded:
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    use_fast=True,
                    **tok_kwargs,
                )
                tokenizer_loaded = True
            except KeyError as e:
                last_tokenizer_error = e
                logging.warning(
                    f"Tokenizer mapping KeyError ({e}). Versuche use_fast=False (Fallback für unbekannte Config)."
                )
            except Exception as e:
                last_tokenizer_error = e
                logging.warning(f"Tokenizer fast fehlgeschlagen: {e}")

        # Schritt 2: AutoTokenizer (slow)
        if not tokenizer_loaded:
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    use_fast=False,
                    **tok_kwargs,
                )
                tokenizer_loaded = True
            except KeyError as e:
                last_tokenizer_error = e
                logging.warning(
                    f"Tokenizer mapping KeyError (slow) ({e}). Prüfe generischen PreTrainedTokenizerFast Fallback."
                )
            except Exception as e:
                last_tokenizer_error = e
                logging.warning(f"Tokenizer slow fehlgeschlagen: {e}")

        # Schritt 3: PreTrainedTokenizerFast direkt (umgeht TOKENIZER_MAPPING)
        if not tokenizer_loaded:
            try:
                self.tokenizer = PreTrainedTokenizerFast.from_pretrained(
                    self.model_name,
                    **tok_kwargs,
                )
                tokenizer_loaded = True
                logging.info(
                    "PreTrainedTokenizerFast Fallback erfolgreich (umging AutoTokenizer Mapping)."
                )
            except Exception as e:
                last_tokenizer_error = e
                logging.warning(
                    f"PreTrainedTokenizerFast Fallback fehlgeschlagen: {e}. Versuche manuellen JSON-Load."
                )

        # Schritt 4: manueller JSON Fallback (nur falls lokaler Cache vorhanden)
        if not tokenizer_loaded:
            try:
                import json

                from huggingface_hub import snapshot_download

                cache_dir = snapshot_download(
                    self.model_name,
                    token=self.hf_token,
                    allow_patterns=[
                        "tokenizer.json",
                        "tokenizer_config.json",
                        "special_tokens_map.json",
                        "vocab.json",
                        "merges.txt",
                    ],
                )
                # Letzter Versuch: PreTrainedTokenizerFast direkt aus tokenizer.json
                tok_json_path = os.path.join(cache_dir, "tokenizer.json")
                if os.path.exists(tok_json_path):
                    self.tokenizer = PreTrainedTokenizerFast(
                        tokenizer_file=tok_json_path
                    )
                    logging.info(
                        "Manueller tokenizer.json Fallback erfolgreich geladen."
                    )
                    tokenizer_loaded = True
                else:
                    raise FileNotFoundError(
                        "tokenizer.json nicht gefunden im heruntergeladenen Snapshot"
                    )
            except Exception as e:
                last_tokenizer_error = e

        if not tokenizer_loaded:
            raise RuntimeError(
                "Tokenizer konnte nicht geladen werden – erwäge Upgrade von transformers (z.B. pip install -U 'transformers>=4.44.0').\n"
                f"Letzter Fehler: {last_tokenizer_error}"
            )

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.tokenizer.model_max_length = getattr(
            config, "max_position_embeddings", 4096
        )
        self.tokenizer.padding_side = "left"

        # device_map immer auto (auch single GPU – spart Code für spätere Multi-GPU)
        device_map = "auto"

        quantization_config = self._build_quant_config()

        common_kwargs = dict(
            config=config,
            torch_dtype=(
                torch.bfloat16
                if self.mixed_precision in {"bf16", "bfloat16", "fp16", "float16"}
                else None
            ),
            device_map=device_map,
            trust_remote_code=True,
        )
        if quantization_config is not None:
            common_kwargs["quantization_config"] = quantization_config

        # Versuche Flash Attention 2 zuerst
        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                attn_implementation="flash_attention_2",
                **common_kwargs,
            )
            logging.info("Flash Attention 2 aktiv.")
        except Exception as e:
            logging.warning(
                f"Flash Attention 2 nicht verfügbar – Standard Attention wird genutzt / oder Fehler: {e}"
            )
            # Entferne evtl. attn_implementation falls inkompatibel
            common_kwargs.pop("attn_implementation", None)
            # Falls Fehler durch Quantisierung ausgelöst wurden -> Retry ohne Quantisierung
            if (
                "get_loading_attributes" in str(e)
                and "quantization_config" in common_kwargs
            ):
                logging.warning(
                    "Fehler durch veraltete bitsandbytes Quantisierungs-API. Lade erneut ohne Quantisierung."
                )
                common_kwargs.pop("quantization_config", None)
            try:
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    **common_kwargs,
                )
            except KeyError as ke:  # typ. Mapping-Problem (z.B. Mistral3Config)
                logging.warning(
                    f"KeyError beim Modell-Mapping: {ke}. Versuche Remote-Code-Fallback erneut."
                )
                # Erzwinge trust_remote_code=True (sicherheitshalber) und entferne evtl. Quantisierung für maximale Kompatibilität
                common_kwargs["trust_remote_code"] = True
                if "quantization_config" in common_kwargs:
                    logging.warning(
                        "Entferne Quantisierung für Kompatibilitäts-Fallback (Mapping KeyError)."
                    )
                    common_kwargs.pop("quantization_config")
                try:
                    self.model = AutoModelForCausalLM.from_pretrained(
                        self.model_name,
                        **common_kwargs,
                    )
                except Exception as ke2:
                    logging.error(
                        "Modell konnte nach KeyError nicht geladen werden. Prüfe transformers Version (pip show transformers) und erwäge ein Upgrade (z.B. pip install -U 'transformers>=4.44.0'). \n"
                        f"Letzter Fehler: {ke2}"
                    )
                    raise
            except Exception as e2:
                logging.error(f"Modell-Ladevorgang fehlgeschlagen: {e2}")
                raise

        # Performance Einstellungen
        try:
            self.model.eval()  # sicherstellen Inferenzmodus
        except Exception:
            pass

        # TF32 für Ampere+ aktivieren (schneller, minimaler Genauigkeitsverlust)
        if torch.cuda.is_available():
            try:
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
            except Exception:
                pass

        # Optionales torch.compile (PyTorch 2, kann mit manchen Quantisierungen inkompatibel sein)
        if os.getenv("LLM_COMPILE", "0").lower() in {"1", "true", "yes"}:
            try:
                compile_mode = os.getenv("LLM_COMPILE_MODE", "reduce-overhead")
                self.model = torch.compile(
                    self.model, mode=compile_mode, fullgraph=False
                )
                logging.info(f"torch.compile aktiviert (mode={compile_mode}).")
            except Exception as e:
                logging.warning(f"torch.compile nicht möglich: {e}")

        end_time = time.time()
        logging.info(
            f"Model {self.model_name} loaded in {end_time - start_time:.2f} seconds."
        )
        try:
            logging.info(f"Model device: {next(self.model.parameters()).device}")
        except StopIteration:
            pass

    def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_new_tokens: int = 150,
    ) -> str:
        logging.info("Starting model call.")
        start_time = time.time()

        # Nachrichtenstruktur (Chat Template fähig)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            tokenized_inputs = self.tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                return_tensors="pt",
            )
            input_ids = tokenized_inputs
            if self.tokenizer.pad_token_id is not None:
                attention_mask = (input_ids != self.tokenizer.pad_token_id).long()
            else:
                attention_mask = torch.ones_like(input_ids)
        except Exception:
            # Fallback: simpler Prompt concat
            full_prompt = (system_prompt + "\n\n" if system_prompt else "") + prompt
            enc = self.tokenizer(
                full_prompt,
                return_tensors="pt",
                truncation=True,
                max_length=self.tokenizer.model_max_length,
            )
            input_ids = enc["input_ids"]
            attention_mask = enc.get("attention_mask")

        device = (
            next(self.model.parameters()).device
            if hasattr(self.model, "parameters")
            else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        )
        input_ids = input_ids.to(device)
        if attention_mask is not None:
            attention_mask = attention_mask.to(device)

        logging.info("Generating response...")
        gen_start = time.time()
        prompt_tokens = input_ids.shape[1]

        try:
            with torch.inference_mode():
                outputs = self.model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    max_new_tokens=max_new_tokens,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    repetition_penalty=1.05,
                    num_return_sequences=1,
                    use_cache=True,
                    output_attentions=False,
                    output_hidden_states=False,
                    return_dict_in_generate=False,
                )
        except RuntimeError as e:
            if "CUDA" in str(e) or "device-side assert" in str(e):
                logging.error(f"CUDA error: {e}")
                logging.info("Greedy Fallback...")
                with torch.inference_mode():
                    outputs = self.model.generate(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        max_new_tokens=min(max_new_tokens, 50),
                        pad_token_id=self.tokenizer.pad_token_id,
                        eos_token_id=self.tokenizer.eos_token_id,
                        do_sample=False,
                        use_cache=True,
                        output_attentions=False,
                        output_hidden_states=False,
                        return_dict_in_generate=False,
                    )
            else:
                raise e

        gen_end = time.time()
        logging.info(f"Response generated in {gen_end - gen_start:.2f} seconds.")

        dec_start = time.time()
        generated_ids = outputs[0, input_ids.shape[1] :]
        gen_tokens = generated_ids.shape[0]
        response = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        dec_end = time.time()
        logging.info(f"Response decoded in {dec_end - dec_start:.2f} seconds.")

        end_time = time.time()
        total = end_time - start_time
        gen_time = gen_end - gen_start
        toks_per_s = gen_tokens / gen_time if gen_time > 0 else float("nan")
        logging.info(
            f"Model call finished in {total:.2f}s (gen {gen_time:.2f}s, prompt_tokens={prompt_tokens}, generated_tokens={gen_tokens}, {toks_per_s:.2f} tok/s)."
        )
        return response.strip()
