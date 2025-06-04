"""
Main script to run the LikertBench evaluation using a specified LLM model.
"""

from llm_handler.model import LLMModel
from notification.telegram_notifier import send_telegram_message
from benchmark.likert_benchmark import run_likert_bench
import os
import torch

def main() -> None:
    # GPU diagnostics
    print(f"🔍 GPU Setup:")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"GPU count: {torch.cuda.device_count()}")
    print(f"CUDA_VISIBLE_DEVICES: {os.environ.get('CUDA_VISIBLE_DEVICES', 'Not set')}")
    
    # Model selection with fallbacks for different GPU configurations
    model_names = [
        # Primary: Large model for multi-GPU setup
        #"meta-llama/Meta-Llama-3-70B-Instruct",
        "meta-llama/Meta-Llama-3-8B-Instruct",
        #"meta-llama/Llama-3.3-70B-Instruct",
        # Fallback: Smaller models if large model fails
        # "mistralai/Mistral-Small-24B-Instruct-2501",
        # "mistralai/Mistral-7B-Instruct-v0.1", 
    ]
    
    successful_runs = 0
    
    for model_name in model_names:
        try:
            print(f"\n🚀 Starting benchmark with model: {model_name}")
            llm = LLMModel(model_identifier=model_name, mixed_precision="fp32")

            summary = run_likert_bench(llm)

            print(f"\n✅ Likert-5 Benchmark Summary for {model_name}:")
            for metric, value in summary.items():
                print(f"{metric}: {value}")
            
            send_telegram_message(
                f"✅ Benchmark completed for {model_name}\n" + 
                f"Likert-5 Summary:\n" + 
                "\n".join(f"{metric}: {value}" for metric, value in summary.items())
            )
            successful_runs += 1
            
        except Exception as e:
            error_msg = f"❌ Failed to run benchmark for {model_name}: {str(e)}"
            print(error_msg)
            send_telegram_message(error_msg)
            
            # If it's a CUDA/GPU error, don't try more models
            if "CUDA" in str(e) or "GPU" in str(e) or "device" in str(e).lower():
                print("🛑 GPU-related error detected. Stopping further model attempts.")
                break
    
    final_msg = f"📊 Benchmark session completed. Successful runs: {successful_runs}/{len(model_names)}"
    print(f"\n{final_msg}")
    send_telegram_message(final_msg)

if __name__ == "__main__":
    print(f"🔍 Process Info: PID={os.getpid()}, CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES')}, GPU_Count={torch.cuda.device_count()}")
    main()
