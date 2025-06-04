#!/bin/bash
# setup_slurm_environment.sh - Setup environment for SLURM cluster

echo "🔧 Setting up SLURM Environment for Multi-GPU Benchmarks"

# Load CUDA modules if available
echo "🚀 Loading CUDA modules..."
if command -v module &> /dev/null; then
    module load cuda/12.6 || echo "⚠️ CUDA module not available"
    module load python/3.10 || echo "⚠️ Python module not available"
    module list
fi

# Check CUDA environment
echo "🔍 CUDA Environment Check:"
echo "CUDA_HOME: ${CUDA_HOME:-'Not set'}"
echo "LD_LIBRARY_PATH: ${LD_LIBRARY_PATH:-'Not set'}"

if command -v nvcc &> /dev/null; then
    echo "✅ nvcc found:"
    nvcc --version
else
    echo "❌ nvcc not found"
fi

# Activate virtual environment
echo "🐍 Activating virtual environment..."
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Upgrade pip and install wheel
echo "📦 Upgrading pip and installing dependencies..."
pip install --upgrade pip setuptools wheel

# Install PyTorch with CUDA support (for cluster environment)
echo "🔥 Installing PyTorch with CUDA support..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126

# Install other requirements
echo "📋 Installing requirements..."
pip install -r requirements.txt

# Verify installation
echo "✅ Verifying PyTorch CUDA installation:"
python3 -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA version: {torch.version.cuda}')
    print(f'Device count: {torch.cuda.device_count()}')
    for i in range(torch.cuda.device_count()):
        try:
            print(f'GPU {i}: {torch.cuda.get_device_name(i)}')
        except Exception as e:
            print(f'GPU {i}: Error - {e}')
else:
    print('❌ CUDA not available in PyTorch')
"

echo "✅ SLURM environment setup completed"
