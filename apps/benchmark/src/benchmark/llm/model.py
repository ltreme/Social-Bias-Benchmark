import logging  # Added for logging
import os
import time  # Added for timing
import warnings
from typing import Dict, Optional

import torch
from huggingface_hub import login
from transformers import (
    AutoConfig,
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)

# Configure basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Suppress some common warnings that might clutter output
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")


class LLMModel:
    def __init__(self, model_identifier: str, mixed_precision: str = "fp16"):
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
        self.model_name = model_identifier
        self.tokenizer = None
        self.model = None
        self._load_model()

    def _load_model(self):
        """
        Loads the tokenizer and the model.
        """
        logging.info(f"Starting to load model: {self.model_name}")
        logging.info(f"Available GPUs: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            logging.info(f"GPU {i}: {torch.cuda.get_device_name(i)}")

        start_time = time.time()
        config = AutoConfig.from_pretrained(self.model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.tokenizer.model_max_length = getattr(
            config, "max_position_embeddings", 4096
        )
        self.tokenizer.padding_side = "left"  # Important for generation

        # Configure device map for multi-GPU setup
        device_map = "auto" if torch.cuda.device_count() > 1 else None

        # Configure proper 4-bit quantization with enhanced stability for large models
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,  # Use bfloat16 for better numerical stability
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_quant_storage=torch.uint8,
        )

        # Try to use Flash Attention 2 if available for better memory efficiency
        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                config=config,
                torch_dtype=torch.bfloat16,  # Use bfloat16 for better numerical stability with large models
                device_map=device_map,
                quantization_config=quantization_config,
                trust_remote_code=True,  # Für einige Modelle erforderlich
                attn_implementation="flash_attention_2",
            )
            logging.info("Using Flash Attention 2 for improved memory efficiency")
        except Exception as e:
            logging.warning(
                f"Flash Attention 2 not available, falling back to standard attention: {e}"
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                config=config,
                torch_dtype=torch.bfloat16,  # Use bfloat16 for better numerical stability with large models
                device_map=device_map,
                quantization_config=quantization_config,
                trust_remote_code=True,  # Für einige Modelle erforderlich
            )

        # Model is automatically distributed with device_map="auto"
        # No need for accelerator.prepare when using device_map

        end_time = time.time()
        logging.info(
            f"Model {self.model_name} loaded in {end_time - start_time:.2f} seconds."
        )
        logging.info(f"Model device: {next(self.model.parameters()).device}")

    def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_new_tokens: int = 150,
    ) -> str:
        """
        Calls the model with a given prompt.

        Args:
            prompt: The main prompt for the model.
            system_prompt: An optional system prompt prepended to the main prompt.
            max_new_tokens: The maximum number of new tokens to generate.

        Returns:
            The model's response as a string.
        """
        logging.info("Starting model call.")
        start_time = time.time()

        # Clear CUDA cache to prevent memory issues
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        input_ids = None
        attention_mask = None

        try:
            # Use apply_chat_template to format the input according to the model's training
            tokenized_inputs = self.tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,  # Ensures the prompt ends correctly for generation
                return_tensors="pt",
                # truncation and padding are generally not applied by apply_chat_template directly for single sequences
                # but it respects tokenizer.model_max_length for truncation if the template is too long.
            )
            input_ids = tokenized_inputs

            if self.tokenizer.pad_token_id is not None:
                attention_mask = (input_ids != self.tokenizer.pad_token_id).long()
            else:
                # If there's no pad_token_id, assume no padding in the input_ids from chat_template for a single sequence
                attention_mask = torch.ones_like(input_ids)

        except Exception as e:
            # print(f"Could not apply chat template: {e}. Using simple concatenation fallback.")
            full_prompt_str = ""
            if system_prompt:
                full_prompt_str += system_prompt + "\\n\\n"
            full_prompt_str += prompt

            encoding = self.tokenizer(
                full_prompt_str,
                return_tensors="pt",
                padding="max_length",  # Pad to max_length to ensure consistent input shape
                truncation=True,
                max_length=self.tokenizer.model_max_length,
            )
            input_ids = encoding["input_ids"]
            attention_mask = encoding[
                "attention_mask"
            ]  # Use attention_mask from tokenizer

        # Move tensors to appropriate device
        device = (
            next(self.model.parameters()).device
            if hasattr(self.model, "parameters")
            else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        )
        input_ids = input_ids.to(device)
        if attention_mask is not None:
            attention_mask = attention_mask.to(device)

        logging.info("Generating response...")
        generation_start_time = time.time()

        try:
            with torch.no_grad():
                # Ensure input_ids are valid (no negative values or out-of-vocab tokens)
                vocab_size = self.model.config.vocab_size
                input_ids = torch.clamp(input_ids, 0, vocab_size - 1)

                # Validate that input_ids don't contain NaN or inf
                if torch.isnan(input_ids).any() or torch.isinf(input_ids).any():
                    raise ValueError("Input contains NaN or inf values")

                outputs = self.model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    max_new_tokens=max_new_tokens,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                    do_sample=True,  # Enable sampling to avoid deterministic issues
                    temperature=0.7,  # Add temperature for stability
                    top_p=0.9,  # Add nucleus sampling
                    repetition_penalty=1.1,  # Prevent repetition loops
                    num_return_sequences=1,
                    use_cache=True,
                    output_attentions=False,
                    output_hidden_states=False,
                    return_dict_in_generate=False,
                )

        except RuntimeError as e:
            if "CUDA" in str(e) or "device-side assert" in str(e):
                logging.error(f"CUDA error during generation: {e}")
                # Try fallback generation with greedy decoding
                logging.info("Attempting fallback generation with greedy decoding...")
                try:
                    with torch.no_grad():
                        outputs = self.model.generate(
                            input_ids=input_ids,
                            attention_mask=attention_mask,
                            max_new_tokens=min(
                                max_new_tokens, 50
                            ),  # Reduce tokens for stability
                            pad_token_id=self.tokenizer.pad_token_id,
                            eos_token_id=self.tokenizer.eos_token_id,
                            do_sample=False,  # Greedy decoding
                            use_cache=True,
                            output_attentions=False,
                            output_hidden_states=False,
                            return_dict_in_generate=False,
                        )
                except Exception as fallback_e:
                    logging.error(f"Fallback generation also failed: {fallback_e}")
                    raise e  # Re-raise original error
            else:
                raise e
        generation_end_time = time.time()
        logging.info(
            f"Response generated in {generation_end_time - generation_start_time:.2f} seconds."
        )

        decoding_start_time = time.time()
        generated_ids = outputs[0, input_ids.shape[1] :]
        response = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        decoding_end_time = time.time()
        logging.info(
            f"Response decoded in {decoding_end_time - decoding_start_time:.2f} seconds."
        )

        end_time = time.time()
        logging.info(f"Model call finished in {end_time - start_time:.2f} seconds.")
        return response.strip()
