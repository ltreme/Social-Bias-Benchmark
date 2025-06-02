from typing import Dict, Optional
import torch
from accelerate import Accelerator
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig # Added AutoConfig

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
        config = AutoConfig.from_pretrained(self.model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Set model_max_length for tokenizer from model config
        # Fallback to a default like 4096 if not available, though it should be for most models.
        self.tokenizer.model_max_length = getattr(config, 'max_position_embeddings', 4096)
        
        # For generation tasks, padding on the left is common.
        self.tokenizer.padding_side = "left"

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            config=config, # Pass the loaded config
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
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            # Use apply_chat_template to format the input according to the model's training
            input_ids = self.tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,  # Ensures the prompt ends correctly for generation
                return_tensors="pt"
            )
        except Exception as e:
            # Fallback to simple concatenation if template fails
            # print(f"Could not apply chat template: {e}. Using simple concatenation.")
            full_prompt_str = ""
            if system_prompt:
                full_prompt_str += system_prompt + "\n\n"
            full_prompt_str += prompt
            # Tokenize the combined string manually
            encoding = self.tokenizer(
                full_prompt_str, return_tensors="pt", padding=True, truncation=True,
                max_length=self.tokenizer.model_max_length
            )
            input_ids = encoding["input_ids"]


        input_ids = input_ids.to(self.accelerator.device)
        
        attention_mask = torch.ones_like(input_ids).to(self.accelerator.device)

        with torch.no_grad():
            outputs = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=max_new_tokens,
                pad_token_id=self.tokenizer.pad_token_id
            )

        generated_ids = outputs[0, input_ids.shape[1]:]
        response = self.tokenizer.decode(generated_ids, skip_special_tokens=True)

        return response.strip()
