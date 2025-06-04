#!/bin/bash
# install_deepspeed.sh — Install DeepSpeed with specific configurations
# This script is designed to be run in a Slurm job environment.


export DS_BUILD_OPS=0
pip install --upgrade pip
pip install deepspeed --no-build-isolation --no-cache-dir