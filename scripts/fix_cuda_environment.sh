#!/bin/bash
# fix_cuda_environment.sh - Fix CUDA environment issues on SLURM

echo "🔧 CUDA Environment Fix"

# Check SLURM GPU allocation
echo "SLURM GPU Info:"
echo "SLURM_GPUS_ON_NODE: ${SLURM_GPUS_ON_NODE:-'Not set'}"
echo "SLURM_JOB_GPUS: ${SLURM_JOB_GPUS:-'Not set'}"
echo "SLURM_LOCALID: ${SLURM_LOCALID:-'Not set'}"

# Force CUDA device reset for problematic GPUs
echo "🔄 Resetting CUDA context..."
python3 -c "
import os
import subprocess

# Try to reset CUDA context
try:
    subprocess.run(['nvidia-smi', '--gpu-reset'], check=False, capture_output=True)
    print('GPU reset attempted')
except:
    print('GPU reset not available')
"

# Test minimal CUDA setup with only working GPU
echo "🧪 Testing individual GPU access..."

# Test GPU 1 only
export CUDA_VISIBLE_DEVICES=1
echo "Testing GPU 1:"
python3 -c "
import torch
if torch.cuda.is_available():
    try:
        device = torch.device('cuda:0')
        test = torch.tensor([1.0]).to(device)
        print(f'✅ GPU 1 working: {torch.cuda.get_device_name(0)}')
    except Exception as e:
        print(f'❌ GPU 1 failed: {e}')
else:
    print('❌ CUDA not available for GPU 1')
"

# Test GPU 3 only
export CUDA_VISIBLE_DEVICES=3
echo "Testing GPU 3:"
python3 -c "
import torch
if torch.cuda.is_available():
    try:
        device = torch.device('cuda:0')
        test = torch.tensor([1.0]).to(device)
        print(f'✅ GPU 3 working: {torch.cuda.get_device_name(0)}')
    except Exception as e:
        print(f'❌ GPU 3 failed: {e}')
else:
    print('❌ CUDA not available for GPU 3')
"

# Determine which GPUs actually work
working_gpus=""
for gpu_id in 1 3; do
    export CUDA_VISIBLE_DEVICES=$gpu_id
    result=$(python3 -c "
import torch
try:
    if torch.cuda.is_available():
        device = torch.device('cuda:0')
        test = torch.tensor([1.0]).to(device)
        print('WORKING')
    else:
        print('FAILED')
except:
    print('FAILED')
" 2>/dev/null)
    
    if [[ "$result" == "WORKING" ]]; then
        if [[ -z "$working_gpus" ]]; then
            working_gpus="$gpu_id"
        else
            working_gpus="$working_gpus,$gpu_id"
        fi
        echo "✅ GPU $gpu_id is functional"
    else
        echo "❌ GPU $gpu_id is not functional"
    fi
done

echo "🎯 Working GPUs: $working_gpus"

# Set optimal CUDA configuration
if [[ -n "$working_gpus" ]]; then
    export CUDA_VISIBLE_DEVICES="$working_gpus"
    echo "✅ Set CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
    
    # Test final configuration
    python3 -c "
import torch
import os
print(f'Final test - CUDA_VISIBLE_DEVICES: {os.environ.get(\"CUDA_VISIBLE_DEVICES\")}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'Device count: {torch.cuda.device_count()}')
if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        try:
            name = torch.cuda.get_device_name(i)
            test = torch.randn(10).cuda(i)
            print(f'✅ GPU {i}: {name} - Working')
        except Exception as e:
            print(f'❌ GPU {i}: Failed - {e}')
"
else
    echo "❌ No working GPUs found!"
    exit 1
fi

echo "✅ CUDA environment fix completed"
