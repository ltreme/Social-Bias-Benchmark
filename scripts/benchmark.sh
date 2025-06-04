#!/bin/bash

echo "🎯 Starting Multi-GPU Benchmark with explicit configuration"

# Use explicit accelerate config and remap GPU IDs for CUDA_VISIBLE_DEVICES
# Since we set CUDA_VISIBLE_DEVICES=1,3, PyTorch sees these as GPU 0,1
accelerate launch \
    --config_file accelerate_config.yaml \
    --num_processes 2 \
    --mixed_precision fp16 \
    app/main.py

echo "✅ Benchmark completed"