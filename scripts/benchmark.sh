#!/bin/bash

accelerate launch app/main.py --model_name "meta-llama/Llama-3.3-70B-Instruct" --benchmark_type "bias" --mixed_precision "fp16"
accelerate launch app/main.py --model_name "mistralai/Mistral-Small-24B-Instruct-2501" --benchmark_type "bias" --mixed_precision "fp16"

echo "✅ Benchmark completed"
