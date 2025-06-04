#!/bin/bash

echo "🎯 Starting Dynamic Multi-GPU Benchmark"

# Generate accelerate config based on available GPUs
echo "🔧 Generating dynamic accelerate configuration..."
bash scripts/generate_accelerate_config.sh

# Check if config was generated successfully
if [ ! -f "accelerate_config.yaml" ]; then
    echo "❌ Failed to generate accelerate config"
    exit 1
fi

# Determine number of processes from config
num_processes=$(grep "num_processes:" accelerate_config.yaml | awk '{print $2}')
use_cpu=$(grep "use_cpu:" accelerate_config.yaml | awk '{print $2}')

echo "📊 Configuration:"
echo "  - Processes: $num_processes"
echo "  - Use CPU: $use_cpu"

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