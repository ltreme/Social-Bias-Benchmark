#!/bin/bash

echo "🎯 Starting Multi-GPU Model Inference Benchmark"

# Set up enhanced CUDA environment for stability
export CUDA_LAUNCH_BLOCKING=1
export TORCH_USE_CUDA_DSA=1
export PYTORCH_CUDA_ALLOC_CONF="max_split_size_mb:512,expandable_segments:True"
export TOKENIZERS_PARALLELISM=false

echo "✅ Enhanced CUDA environment configured"

echo "📊 Runtime Configuration:"
echo "  - CUDA_VISIBLE_DEVICES: ${CUDA_VISIBLE_DEVICES:-'Not set'}"
echo "  - Available GPUs: $(python -c 'import torch; print(torch.cuda.device_count())')"

# Show GPU status
echo "🔍 GPU Memory Status:"
python -c "
import torch
if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        memory_gb = props.total_memory / 1024**3
        print(f'  GPU {i}: {torch.cuda.get_device_name(i)} - {memory_gb:.1f}GB')
else:
    print('  No CUDA GPUs available')
"

echo "🚀 Starting single-process multi-GPU inference"
echo "  - Model will be automatically distributed across available GPUs"
echo "  - Using HuggingFace device_map='auto' for optimal GPU distribution"

# Start the benchmark directly with Python (no accelerate launch needed)
# Using improved model.py with bfloat16 and enhanced error handling
python app/main.py

echo "✅ Benchmark completed"