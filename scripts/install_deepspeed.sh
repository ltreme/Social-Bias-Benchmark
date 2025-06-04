#!/bin/bash
#SBATCH --job-name=install-deepspeed
#SBATCH --output=install-deepspeed-%j.out
#SBATCH --gres=gpu:a6000:1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00

cd "$SLURM_SUBMIT_DIR"
source venv/bin/activate

# Empfohlen: Build-Operatoren deaktivieren, um Build-Probleme zu vermeiden
export DS_BUILD_OPS=0
pip install --upgrade pip
pip install deepspeed --no-build-isolation --no-cache-dir