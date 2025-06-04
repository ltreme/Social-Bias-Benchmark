#!/bin/bash

echo "🧪 Testing Multi-GPU Configuration"

# Test GPU visibility
echo "=== GPU Visibility Test ==="
export CUDA_VISIBLE_DEVICES=1,3
echo "CUDA_VISIBLE_DEVICES: $CUDA_VISIBLE_DEVICES"

python3 -c "
import torch
import os

print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'CUDA version: {torch.version.cuda}')
print(f'Device count: {torch.cuda.device_count()}')
print(f'CUDA_VISIBLE_DEVICES: {os.environ.get(\"CUDA_VISIBLE_DEVICES\", \"Not set\")}')

for i in range(torch.cuda.device_count()):
    device = torch.device(f'cuda:{i}')
    print(f'GPU {i}: {torch.cuda.get_device_name(device)} - Memory: {torch.cuda.get_device_properties(device).total_memory / 1024**3:.1f}GB')
    
    # Test tensor creation on each device
    try:
        test_tensor = torch.randn(100, 100).to(device)
        print(f'  ✅ Tensor creation successful on GPU {i}')
    except Exception as e:
        print(f'  ❌ Tensor creation failed on GPU {i}: {e}')
"

echo ""
echo "=== Accelerate Configuration Test ==="
if [ -f "accelerate_config.yaml" ]; then
    echo "✅ accelerate_config.yaml found"
    echo "Config contents:"
    cat accelerate_config.yaml
else
    echo "❌ accelerate_config.yaml not found"
fi

echo ""
echo "=== HuggingFace Token Test ==="
if [ -f ".env" ]; then
    source .env
    if [ -n "$HF_TOKEN" ]; then
        echo "✅ HF_TOKEN found in .env"
        python3 -c "
import os
from huggingface_hub import login
try:
    login(token=os.getenv('HF_TOKEN'))
    print('✅ HuggingFace authentication successful')
except Exception as e:
    print(f'❌ HuggingFace authentication failed: {e}')
"
    else
        echo "❌ HF_TOKEN not found in .env"
    fi
else
    echo "❌ .env file not found"
fi

echo ""
echo "🧪 Configuration test completed"
