### Start Slurm job with this command:
```sh
sbatch scripts/run_slurm.sh <COMMAND OR SCRIPT>
```

### Start Benchmark:
```sh
# Multi-GPU (2 GPUs) - Primary option
sbatch scripts/run_slurm.sh scripts/benchmark.sh

# Single GPU - Fallback for hardware issues
chmod +x start_single_gpu.sh
./start_single_gpu.sh
```

### Debug GPU Issues:
```sh
# Test GPU configuration on SLURM cluster
chmod +x submit_gpu_test.sh
./submit_gpu_test.sh

# Fix CUDA environment on cluster
sbatch scripts/run_slurm.sh scripts/fix_cuda_environment.sh

# Generate dynamic accelerate config on cluster  
sbatch scripts/run_slurm.sh scripts/generate_accelerate_config.sh
```

### Troubleshooting:
- **GPU Hardware Issues**: Use single GPU fallback with `./start_single_gpu.sh`
- **PyTorch "No CUDA GPUs available"**: Run CUDA environment fix
- **GPU allocation issues**: Check `nvidia-smi` output and SLURM logs
- **HuggingFace access errors**: Ensure HF_TOKEN is set in .env file
- **Multi-GPU fails**: Try single GPU option which avoids broken GPU 0