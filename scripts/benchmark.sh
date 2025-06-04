#!/bin/bash

echo "🎯 Starting Dynamic Multi-GPU Benchmark"

# Check for dynamic config from CUDA fix first
if [ -f "accelerate_config_dynamic.yaml" ]; then
    CONFIG_FILE="accelerate_config_dynamic.yaml"
    echo "✅ Using dynamic config from CUDA environment fix"
    cp accelerate_config_dynamic.yaml accelerate_config.yaml
elif [ -f "accelerate_config.yaml" ]; then
    CONFIG_FILE="accelerate_config.yaml"
    echo "📋 Using existing accelerate config"
else
    # Generate accelerate config based on available GPUs
    echo "🔧 Generating dynamic accelerate configuration..."
    bash scripts/generate_accelerate_config.sh
    CONFIG_FILE="accelerate_config.yaml"
fi

# Check if config exists
if [ ! -f "accelerate_config.yaml" ]; then
    echo "❌ Failed to find or generate accelerate config"
    exit 1
fi

echo "📄 Active configuration:"
cat accelerate_config.yaml

# Determine number of processes from config
num_processes=$(grep "num_processes:" accelerate_config.yaml | awk '{print $2}')
use_cpu=$(grep "use_cpu:" accelerate_config.yaml | awk '{print $2}')

echo "📊 Runtime Configuration:"
echo "  - Config file: $CONFIG_FILE"
echo "  - Processes: $num_processes"
echo "  - Use CPU: $use_cpu"
echo "  - CUDA_VISIBLE_DEVICES: ${CUDA_VISIBLE_DEVICES:-'Not set'}"

# Launch with appropriate configuration
if [[ "$use_cpu" == "true" ]]; then
    echo "🖥️ Running on CPU (no GPUs available)"
    accelerate launch \
        --config_file accelerate_config.yaml \
        app/main.py
else
    echo "🚀 Running on GPU(s) with $num_processes process(es)"
    accelerate launch \
        --config_file accelerate_config.yaml \
        --num_processes "$num_processes" \
        --mixed_precision fp16 \
        app/main.py
fi

echo "✅ Benchmark completed"