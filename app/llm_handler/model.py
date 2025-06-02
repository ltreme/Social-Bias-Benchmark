from typing import Dict, Optional
import torch
from accelerate import Accelerator
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig
import time # Added for timing
import logging # Added for logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class LLMModel:
    def __init__(self, model_identifier: str, mixed_precision: str = "fp16"):
        """
        Initialize the LLM model.

        Args:
            model_identifier: The identifier of the model on Hugging Face.
            mixed_precision: The mixed precision to use (e.g., "fp16", "bf16").
        """
        self.accelerator = Accelerator(mixed_precision=mixed_precision)
        self.model_name = model_identifier
        self.tokenizer = None
        self.model = None
        self._load_model()

    def _load_model(self):
        """
        Loads the tokenizer and the model.
        """
        logging.info(f"Starting to load model: {self.model_name}")
        start_time = time.time()
        config = AutoConfig.from_pretrained(self.model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            # If pad_token was initially None and set to eos_token,
            # make sure the model's config also reflects this for generation.
            # config.pad_token_id = self.tokenizer.eos_token_id # This might be needed for some models

        self.tokenizer.model_max_length = getattr(config, 'max_position_embeddings', 4096)
        self.tokenizer.padding_side = "left" # Important for generation

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            config=config, 
            torch_dtype=torch.float16 if self.accelerator.mixed_precision == "fp16" else torch.bfloat16
        )
        
        # If pad_token was added or changed, and it resulted in a new token ID being effectively used
        # (e.g. if eos_token wasn't properly registered as pad before),
        # resizing embeddings might be necessary. However, eos_token should always be known.
        # self.model.resize_token_embeddings(len(self.tokenizer))

        self.model = self.accelerator.prepare(self.model)
        end_time = time.time()
        logging.info(f"Model {self.model_name} loaded in {end_time - start_time:.2f} seconds.")

    def call(self, prompt: str, system_prompt: Optional[str] = None, max_new_tokens: int = 150) -> str:
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
                return_tensors="pt"
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
                full_prompt_str, return_tensors="pt", 
                padding="max_length", # Pad to max_length to ensure consistent input shape
                truncation=True,
                max_length=self.tokenizer.model_max_length
            )
            input_ids = encoding["input_ids"]
            attention_mask = encoding["attention_mask"] # Use attention_mask from tokenizer

        input_ids = input_ids.to(self.accelerator.device)
        if attention_mask is not None: # Ensure attention_mask is not None before moving
            attention_mask = attention_mask.to(self.accelerator.device)

        logging.info("Generating response...")
        generation_start_time = time.time()
        with torch.no_grad():
            outputs = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask, # Pass attention_mask if available
                max_new_tokens=max_new_tokens,
                pad_token_id=self.tokenizer.pad_token_id
            )
        generation_end_time = time.time()
        logging.info(f"Response generated in {generation_end_time - generation_start_time:.2f} seconds.")

        decoding_start_time = time.time()
        generated_ids = outputs[0, input_ids.shape[1]:]
        response = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        decoding_end_time = time.time()
        logging.info(f"Response decoded in {decoding_end_time - decoding_start_time:.2f} seconds.")

        end_time = time.time()
        logging.info(f"Model call finished in {end_time - start_time:.2f} seconds.")
        return response.strip()
