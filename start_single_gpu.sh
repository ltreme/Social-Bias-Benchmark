#!/bin/bash

echo "🚀 Starting Single GPU Benchmark (Fallback Strategy)"
echo "This uses only 1 GPU to avoid the hardware issues with GPU 0"

# Ensure logs directory exists
mkdir -p logs

# Make script executable
chmod +x scripts/run_slurm_single.sh

# Submit the single GPU job
job_id=$(sbatch --parsable scripts/run_slurm_single.sh scripts/benchmark.sh)

echo "✅ Single GPU job submitted with ID: $job_id"
echo "📊 Monitor with: squeue -j $job_id"
echo "📝 View logs with: tail -f logs/slurm-single-$job_id.out"
echo ""
echo "💡 This avoids the broken GPU 0 by requesting only 1 working GPU"
