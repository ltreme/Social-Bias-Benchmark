"""
Main script to run the LikertBench evaluation using a specified LLM model.
"""

from llm_handler.model import LLMModel
from notification.telegram_notifier import send_telegram_message
from benchmark.likert_benchmark import run_likert_bench

def main() -> None:
    # 1. Modell-Wrapper initialisieren
    # model_name = "mistralai/Mistral-7B-Instruct-v0.1"
    model_name = "mistralai/Mistral-Small-24B-Instruct-2501"
    llm = LLMModel(model_identifier=model_name, mixed_precision="fp16")

    summary = run_likert_bench(llm)

    print("Likert-5 Benchmark Summary:")
    for metric, value in summary.items():
        print(f"{metric}: {value}")
    send_telegram_message(
        f"Likert-5 Benchmark Summary:\n" + "\n".join(f"{metric}: {value}" for metric, value in summary.items())
    )

if __name__ == "__main__":
    main()
