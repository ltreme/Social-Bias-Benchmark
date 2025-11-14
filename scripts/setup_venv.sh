rm -rf venv
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r apps/requirements-dev.txt
cd apps/backend
pip install -e .
cd - >/dev/null
