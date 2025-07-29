#!/bin/bash

# Deactivate conda envs if they exist to avoid conflicts
if [ -n "$CONDA_SHLVL" ] && [ "$CONDA_SHLVL" -gt 0 ]; then
    echo "Deactivating conda environment..."
    conda deactivate
fi

# Activate the project's virtual environment
source venv/bin/activate

# Set the project root directory
PROJECT_ROOT=$(pwd)

# Set PYTHONPATH directly for the command to ensure it's correctly applied
echo "Running benchmark preprocessing script..."
PYTHONPATH=$PROJECT_ROOT/apps/shared/src:$PROJECT_ROOT/apps/persona_generator/src:$PROJECT_ROOT/apps/benchmark/src python -m benchmark.cli.run_preprocessing "$@"
echo "✅ Benchmark preprocessing completed"