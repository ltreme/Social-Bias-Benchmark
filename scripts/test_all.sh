#!/bin/bash
set -e

source venv/bin/activate
python -m unittest discover apps/persona_generator/tests -p "*.py" -v
python -m unittest discover apps/benchmark/tests -p "*.py" -v
