"""
Main script to run the LikertBench evaluation using a specified LLM model.
"""

import argparse
import os

import torch

from benchmark.benchmarks.bias_benchmark import BiasBenchmark
from benchmark.benchmarks.likert_benchmark import LikertBenchmark
from benchmark.llm.model import LLMModel
from shared.notification.telegram_notifier import send_telegram_message


def run_specific_benchmark(
    model_identifier: str, benchmark_type: str, mixed_precision: str
) -> bool:
    """
    Runs a specific benchmark with the given LLM model.
    Returns True on success, False otherwise.
    """
    try:
        print(
            f"\n🚀 Initializing LLM: {model_identifier} with precision: {mixed_precision}"
        )
        llm = LLMModel(
            model_identifier=model_identifier, mixed_precision=mixed_precision
        )

        benchmark_instance = None
        benchmark_name_display = ""

        if benchmark_type == "likert":
            benchmark_instance = LikertBenchmark(model=llm)
            benchmark_name_display = "Likert Benchmark"
        elif benchmark_type == "bias":
            benchmark_instance = BiasBenchmark(model=llm)
            benchmark_name_display = "Bias Benchmark"
        else:
            error_msg = f"❌ Unknown benchmark type: {benchmark_type}"
            print(error_msg)
            send_telegram_message(error_msg)
            return False

        print(f"\n🚀 Starting {benchmark_name_display} for model: {model_identifier}")
        benchmark_instance.run()
        summary = benchmark_instance.report()

        print(f"\n✅ {benchmark_name_display} summary for {model_identifier}:")
        summary_text_parts = []
        for metric, value in summary.items():
            print(f"{metric}: {value}")
            summary_text_parts.append(f"{metric}: {value}")

        send_telegram_message(
            f"✅ {benchmark_name_display} completed for {model_identifier}\n"
            + f"Summary:\n"
            + "\n".join(summary_text_parts)
        )
        return True

    except Exception as e:
        error_msg = f"❌ Error running {benchmark_type} benchmark for {model_identifier}: {str(e)}"
        print(error_msg)
        send_telegram_message(error_msg)
        if "CUDA" in str(e) or "GPU" in str(e) or "device" in str(e).lower():
            print("ℹ️ GPU-related error detected during execution.")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LLM Benchmarks.")
    parser.add_argument(
        "--model_name",
        type=str,
        required=True,
        help="Identifier of the LLM model to use (e.g. 'meta-llama/Llama-3.3-70B-Instruct')",
    )
    parser.add_argument(
        "--benchmark_type",
        type=str,
        required=True,
        choices=["likert", "bias"],
        help="Type of benchmark to run ('likert' or 'bias')",
    )
    parser.add_argument(
        "--mixed_precision",
        type=str,
        default="fp16",
        help="Mixed Precision for the model (e.g. 'fp16', 'bf16', default: 'fp16')",
    )
    # Additional arguments can be added here, e.g. paths to data,
    # if not hard-coded in the benchmark classes.

    args = parser.parse_args()

    # GPU diagnostics
    print(f"🔍 GPU Setup:")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"GPU count: {torch.cuda.device_count()}")
    print(f"CUDA_VISIBLE_DEVICES: {os.environ.get('CUDA_VISIBLE_DEVICES', 'Not set')}")

    # Run the specific benchmark with the provided arguments
    success = run_specific_benchmark(
        args.model_name, args.benchmark_type, args.mixed_precision
    )

    final_msg_outcome = "successful" if success else "failed"
    final_msg = f"📊 Benchmark run for {args.model_name} on {args.benchmark_type} benchmark {final_msg_outcome}."
    print(f"\n{final_msg}")
    send_telegram_message(final_msg)


if __name__ == "__main__":
    print(
        f"🔍 Process Info: PID={os.getpid()}, CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES')}, GPU_Count={torch.cuda.device_count()}"
    )
    main()
