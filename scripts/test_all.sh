#!/bin/bash
set -e

source venv/bin/activate
export PYTHONPATH=apps/backend/src
python -m unittest discover apps/backend/tests/persona -p "test_*.py" -v
python -m unittest discover apps/backend/tests/benchmark -p "test_*.py" -v
