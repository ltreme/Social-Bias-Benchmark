from typing import Dict, Optional
import torch
from accelerate import Accelerator
from transformers import AutoTokenizer, AutoModelForCausalLM

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
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        # Set default padding token if not present
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.float16 if self.accelerator.mixed_precision == "fp16" else torch.bfloat16
            # Additional configuration for loading the model can be added here
        )
        self.model = self.accelerator.prepare(self.model)

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
        full_prompt = prompt
        if system_prompt:
            # Simple concatenation for the system prompt.
            # Some models may require a specific formatting template.
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # Tokenize on CPU
        encoding = self.tokenizer(
            full_prompt, return_tensors="pt", padding=True, truncation=True
        )
        input_ids = encoding["input_ids"]
        attention_mask = encoding["attention_mask"]

        # Manually move input tensors to the accelerator device
        device = self.accelerator.device
        input_ids = input_ids.to(device)
        attention_mask = attention_mask.to(device)

        # Generating
        with torch.no_grad(): # Important for inference to disable gradient calculations
            outputs = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=max_new_tokens,
                pad_token_id=self.tokenizer.pad_token_id # explicitly set pad_token_id
            )

        # Decode and return result (Decoding on CPU)
        # Only decode the generated part, not the prompt
        generated_ids = outputs[0, input_ids.shape[1]:]
        response = self.tokenizer.decode(generated_ids, skip_special_tokens=True)

        return response.strip()
