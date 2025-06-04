#!/bin/bash

accelerate launch --num_processes 2 --mixed_precision=fp16 app/main.py