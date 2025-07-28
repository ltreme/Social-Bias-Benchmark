rm -rf venv
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r apps/requirements-dev.txt
cd apps/shared
pip install -e .
cd ../persona_generator
pip install -e .
cd ../benchmark
pip install -e .