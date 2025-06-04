#!/bin/bash

echo "🚀 Submitting GPU Test Job to SLURM Cluster"

# Ensure logs directory exists
mkdir -p logs

# Make script executable
chmod +x scripts/test_slurm_gpu.sh

# Submit the test job
job_id=$(sbatch --parsable scripts/test_slurm_gpu.sh)

echo "✅ GPU test job submitted with ID: $job_id"
echo "📊 Monitor with: squeue -j $job_id"
echo "📝 View logs with: tail -f logs/gpu-test-$job_id.out"
echo ""
echo "💡 Tip: Once job completes, check the log for GPU detection results"
