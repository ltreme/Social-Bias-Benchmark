"""
Hello-World for Mistral-7B using transformers + accelerate.
"""

from typing import Dict
import torch
from accelerate import Accelerator
from transformers import AutoTokenizer, AutoModelForCausalLM

def main() -> None:
    # 1. Initialize accelerator for device & mixed-precision management
    accelerator: Accelerator = Accelerator(mixed_precision="fp16")

    # 2. Model identifier (will be downloaded if not present)
    model_name: str = "mistralai/Mistral-7B-Instruct"

    # 3. Load tokenizer and model (half-precision for memory savings)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16
    )

    # 4. Prepare model for distributed inference
    model = accelerator.prepare(model)

    # 5. Define a fun test prompt
    prompt: str = (
        "You are a cat who just visited a new cat-themed café. "
        "Write a humorous review from your feline point of view."
    )

    # 6. Tokenize, move inputs to device and generate
    inputs: Dict[str, torch.Tensor] = tokenizer(prompt, return_tensors="pt", padding=True)
    inputs = accelerator.prepare(inputs)
    outputs = model.generate(**inputs, max_new_tokens=100)

    # 7. Decode and print
    response: str = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print("\n=== Prompt ===")
    print(prompt)
    print("\n=== Response ===")
    print(response)

if __name__ == "__main__":
    main()
