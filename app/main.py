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
    model_name: str = "mistralai/Mistral-7B-Instruct-v0.1"

    # 3. Load tokenizer and model (half-precision for memory savings)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.pad_token = tokenizer.eos_token  # use eos as pad_token
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16
    )

    # 4. Prepare model for distributed inference
    model = accelerator.prepare(model)

    # 5. Define prompt
    prompt: str = (
        "You are a cat who just visited a new cat-themed café. "
        "Write a humorous review from your feline point of view."
    )

    # 6. Tokenize on CPU
    encoding: Dict[str, torch.Tensor] = tokenizer(
        prompt, return_tensors="pt", padding=True
    )
    input_ids = encoding["input_ids"]
    attention_mask = encoding["attention_mask"]

    # 7. Manually move input tensors to the accelerator device
    device = accelerator.device
    input_ids = input_ids.to(device)
    attention_mask = attention_mask.to(device)

    # 8. Generate continuation
    outputs = model.generate(
        input_ids=input_ids,
        attention_mask=attention_mask,
        max_new_tokens=100
    )

    # 9. Decode and print result (decode on CPU)
    if accelerator.num_processes > 1:
        # gather outputs across GPUs
        outputs = accelerator.gather(outputs)
    generated = outputs[0]
    response: str = tokenizer.decode(generated, skip_special_tokens=True)

    print("\n=== Prompt ===")
    print(prompt)
    print("\n=== Response ===")
    print(response)


if __name__ == "__main__":
    main()
