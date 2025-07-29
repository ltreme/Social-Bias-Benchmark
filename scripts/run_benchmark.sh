#!/bin/bash

# Set the project root directory
PROJECT_ROOT=$(pwd)

# Add the src directory to the PYTHONPATH
export PYTHONPATH=$PROJECT_ROOT/apps/benchmark/src:$PYTHONPATH

# Run the preprocessing script as a module
python -m benchmark.cli.run_preprocessing "$@"
