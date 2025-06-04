"""
Main script to run the LikertBench evaluation using a specified LLM model.
"""

from llm_handler.model import LLMModel
from notification.telegram_notifier import send_telegram_message
from benchmark.likert_benchmark import run_likert_bench
import os
import torch

def main() -> None:
    # 1. Modell-Wrapper initialisieren
    # model_name = "mistralai/Mistral-7B-Instruct-v0.1"
    model_names = [
        #"mistralai/Mistral-Small-24B-Instruct-2501",
        #"mistralai/Mistral-7B-Instruct-v0.1", 
        "meta-llama/Llama-3.3-70B-Instruct",
    ]
    for model_name in model_names:
        llm = LLMModel(model_identifier=model_name, mixed_precision="fp16")

        summary = run_likert_bench(llm)

        print("Likert-5 Benchmark Summary:")
        for metric, value in summary.items():
            print(f"{metric}: {value}")
        send_telegram_message(
            f"Likert-5 Benchmark Summary:\n" + "\n".join(f"{metric}: {value}" for metric, value in summary.items())
        )

if __name__ == "__main__":

    print(f"RANK={os.environ.get('RANK')}, LOCAL_RANK={os.environ.get('LOCAL_RANK')}, CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES')}, torch.cuda.device_count()={torch.cuda.device_count()}")

    main()
