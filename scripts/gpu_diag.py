import os

import torch


def main():
    print(f"TORCH_USE_CUDA_DSA from Python env: {os.environ.get('TORCH_USE_CUDA_DSA')}")
    print(f"PyTorch version: {torch.__version__}")

    cuda_available = torch.cuda.is_available()
    print(f"CUDA available: {cuda_available}")

    # Diese Umgebungsvariable immer ausgeben, da sie von Slurm gesetzt wird
    print(
        f"CUDA_VISIBLE_DEVICES from Python env: {os.environ.get('CUDA_VISIBLE_DEVICES')}"
    )

    if cuda_available:
        print(f"CUDA version used by PyTorch: {torch.version.cuda}")
        num_gpus_pytorch = torch.cuda.device_count()
        print(f"Number of GPUs PyTorch can use: {num_gpus_pytorch}")
        for i in range(num_gpus_pytorch):
            print(f"PyTorch - GPU {i} (logical index): {torch.cuda.get_device_name(i)}")
            try:
                print(
                    f"  Memory Allocated (GPU {i}): {torch.cuda.memory_allocated(i)/1024**2:.2f} MB"
                )
                print(
                    f"  Memory Reserved (GPU {i}): {torch.cuda.memory_reserved(i)/1024**2:.2f} MB"
                )
                # Attempt a simple operation on the GPU
                x = torch.tensor([1.0, 2.0]).cuda(i)
                print(f"  Simple tensor operation on GPU {i} successful: {x}")
            except Exception as e:
                print(f"  Error during PyTorch operation on GPU {i}: {e}")
    else:
        print("PyTorch reports CUDA is not available.")
        # Versuchen, die Geräteanzahl trotzdem abzufragen; kann Hinweise geben oder einen Fehler auslösen
        try:
            # Dies bezieht sich auf die Anzahl der GPUs, die PyTorch *sehen* würde, wenn CUDA initialisiert werden könnte,
            # basierend auf CUDA_VISIBLE_DEVICES.
            num_gpus_reported_by_driver_if_cuda_worked = torch.cuda.device_count()
            print(
                f"torch.cuda.device_count() reports: {num_gpus_reported_by_driver_if_cuda_worked}"
            )
            print(
                f"(This value reflects GPUs visible via CUDA_VISIBLE_DEVICES, but PyTorch cannot initialize its CUDA context for them.)"
            )

        except Exception as e:
            # Häufiger ist RuntimeError: No CUDA GPUs are available, wenn is_available() False ist.
            print(
                f"Error calling torch.cuda.device_count() when CUDA not available: {e}"
            )


if __name__ == "__main__":
    main()
