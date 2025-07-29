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

# Add the src directory to the PYTHONPATH
export PYTHONPATH=$PROJECT_ROOT/apps/benchmark/src:$PYTHONPATH

# Run the preprocessing script as a module
echo "Running benchmark preprocessing script..."
python -m benchmark.cli.run_preprocessing "$@"
echo "✅ Benchmark preprocessing completed"