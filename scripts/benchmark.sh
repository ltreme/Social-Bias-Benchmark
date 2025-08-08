#!/bin/bash

#python apps/benchmark/src/benchmark/cli/run_preprocessing.py --model_name mistralai/Mistral-Small-24B-Instruct-2501

python apps/benchmark/src/benchmark/cli/run_bias_benchmark.py --model_name mistralai/Mistral-Small-24B-Instruct-2501

echo "✅ Benchmark completed"