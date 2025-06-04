import torch
import os
print(f"TORCH_USE_CUDA_DSA from Python env: {os.environ.get('TORCH_USE_CUDA_DSA')}")
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'CUDA version: {torch.version.cuda if torch.cuda.is_available() else 'N/A'}')
print(f'Device count: {torch.cuda.device_count()}')
print(f'CUDA_VISIBLE_DEVICES: {os.environ.get('CUDA_VISIBLE_DEVICES', 'Not set')}')
if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        try:
            device = torch.device(f'cuda:{i}')
            name = torch.cuda.get_device_name(device)
            props = torch.cuda.get_device_properties(device)
            print(f'GPU {i}: {name} - {props.total_memory / 1024**3:.1f}GB')
        except Exception as e:
            print(f'GPU {i}: Error - {str(e)[:50]}...')
