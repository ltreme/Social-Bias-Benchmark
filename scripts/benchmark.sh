#!/bin/bash

accelerate launch --num_processes 4 --mixed_precision=fp16 app/main.py