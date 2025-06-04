#!/bin/bash

echo "🧪 Testing Multi-GPU Configuration (Local Development Only)"
echo "⚠️  Note: This test runs locally and won't show cluster GPUs"
echo "🎯 For cluster GPU testing, use: ./submit_gpu_test.sh"
echo ""
echo "Current working directory: $(pwd)"

# Test different CUDA_VISIBLE_DEVICES configurations
echo "=== CUDA Environment Test ==="
echo "Original CUDA_VISIBLE_DEVICES: ${CUDA_VISIBLE_DEVICES:-'Not set'}"

# Test 1: Reset CUDA environment
unset CUDA_VISIBLE_DEVICES
echo "Test 1 - No CUDA_VISIBLE_DEVICES restriction:"
python3 -c "
import torch
import os
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'Device count: {torch.cuda.device_count()}')
if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        try:
            print(f'GPU {i}: {torch.cuda.get_device_name(i)}')
        except Exception as e:
            print(f'GPU {i}: Error - {e}')
"

# Test 2: Only GPU 1
export CUDA_VISIBLE_DEVICES=1
echo ""
echo "Test 2 - CUDA_VISIBLE_DEVICES=1:"
python3 -c "
import torch
import os
print(f'CUDA_VISIBLE_DEVICES: {os.environ.get(\"CUDA_VISIBLE_DEVICES\", \"Not set\")}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'Device count: {torch.cuda.device_count()}')
if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        try:
            print(f'GPU {i}: {torch.cuda.get_device_name(i)}')
            # Test tensor creation
            test_tensor = torch.randn(10, 10).cuda(i)
            print(f'  ✅ Tensor creation successful on GPU {i}')
        except Exception as e:
            print(f'  ❌ GPU {i}: Error - {e}')
"

# Test 3: Only GPU 3  
export CUDA_VISIBLE_DEVICES=3
echo ""
echo "Test 3 - CUDA_VISIBLE_DEVICES=3:"
python3 -c "
import torch
import os
print(f'CUDA_VISIBLE_DEVICES: {os.environ.get(\"CUDA_VISIBLE_DEVICES\", \"Not set\")}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'Device count: {torch.cuda.device_count()}')
if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        try:
            print(f'GPU {i}: {torch.cuda.get_device_name(i)}')
            # Test tensor creation
            test_tensor = torch.randn(10, 10).cuda(i)
            print(f'  ✅ Tensor creation successful on GPU {i}')
        except Exception as e:
            print(f'  ❌ GPU {i}: Error - {e}')
"

# Test 4: Both GPUs individually detected
export CUDA_VISIBLE_DEVICES=1,3
echo ""
echo "Test 4 - CUDA_VISIBLE_DEVICES=1,3:"
python3 -c "
import torch
import os
print(f'CUDA_VISIBLE_DEVICES: {os.environ.get(\"CUDA_VISIBLE_DEVICES\", \"Not set\")}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'Device count: {torch.cuda.device_count()}')
if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        try:
            print(f'GPU {i}: {torch.cuda.get_device_name(i)}')
            # Test tensor creation
            test_tensor = torch.randn(10, 10).cuda(i)
            print(f'  ✅ Tensor creation successful on GPU {i}')
        except Exception as e:
            print(f'  ❌ GPU {i}: Error - {e}')
"

echo ""
echo "=== CUDA Runtime and Driver Test ==="
python3 -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA version (runtime): {torch.version.cuda}')
print(f'cuDNN version: {torch.backends.cudnn.version()}')
print(f'CUDA available: {torch.cuda.is_available()}')

# Check CUDA initialization
try:
    torch.cuda.init()
    print('✅ CUDA initialization successful')
except Exception as e:
    print(f'❌ CUDA initialization failed: {e}')
"

echo ""
echo "=== System CUDA Information ==="
if command -v nvcc &> /dev/null; then
    echo "nvcc version:"
    nvcc --version
else
    echo "❌ nvcc not found"
fi

echo ""
echo "=== nvidia-ml-py Test ==="
python3 -c "
try:
    import pynvml
    pynvml.nvmlInit()
    count = pynvml.nvmlDeviceGetCount()
    print(f'NVML device count: {count}')
    for i in range(count):
        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
        name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
        print(f'NVML GPU {i}: {name}')
    print('✅ NVML working correctly')
except Exception as e:
    print(f'❌ NVML error: {e}')
"

echo ""
echo "🧪 GPU configuration test completed"
