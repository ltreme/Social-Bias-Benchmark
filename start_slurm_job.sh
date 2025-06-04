#!/bin/bash

echo "🚀 Starting SLURM Multi-GPU Benchmark Job"

# Pre-flight checks
echo "=== Pre-flight Checks ==="

# Check if required files exist
required_files=("scripts/run_slurm.sh" "scripts/benchmark.sh" "scripts/fix_cuda_environment.sh" "scripts/generate_accelerate_config.sh")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Required file not found: $file"
        exit 1
    fi
done

if [ ! -f ".env" ]; then
    echo "⚠️ .env file not found. HuggingFace gated models may not be accessible."
    echo "Please create .env with HF_TOKEN if you need access to gated models."
fi

echo "✅ All required files found"

# Test GPU configuration locally (if CUDA is available)
if command -v nvidia-smi &> /dev/null; then
    echo "=== Local GPU Status ==="
    nvidia-smi --query-gpu=index,name,memory.total,temperature.gpu,pstate --format=csv,noheader,nounits
fi

# Make scripts executable
chmod +x scripts/*.sh

echo "=== Submitting SLURM Job ==="
sbatch scripts/run_slurm.sh scripts/benchmark.sh

echo "✅ Job submitted. Monitor with: squeue -u $USER"
echo "📝 Check logs in: logs/"
