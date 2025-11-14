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
echo "[deprecated] Dieses Skript wurde vom neuen Backend-CLI ersetzt."
echo "Nutze z. B.:"
echo "  PYTHONPATH=$PROJECT_ROOT/apps/backend/src python -m backend.application.cli.run_attr_generation --help"
exit 1
