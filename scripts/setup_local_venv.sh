#!/bin/bash
# Setup local virtual environment that mirrors the Docker container
# This provides Intellisense while you can still run code in Docker

set -e

echo "Creating local venv for Intellisense..."

# Create venv in project root
python3.11 -m venv .venv

# Activate it
source .venv/bin/activate

# Install same dependencies as container
pip install --upgrade pip setuptools wheel
pip install -r apps/backend/requirements.txt

# Install dev dependencies if available
if [ -f apps/requirements-dev.txt ]; then
    pip install -r apps/requirements-dev.txt
fi

echo ""
echo "✅ Local venv created successfully!"
echo ""
echo "VS Code will use this for Intellisense."
echo "To run code in Docker, use the docker-python.sh wrapper."
echo ""
echo "Select interpreter: Cmd+Shift+P -> 'Python: Select Interpreter' -> .venv"
