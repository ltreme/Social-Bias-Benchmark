#!/bin/bash

accelerate launch app/main.py --num_processes 4 --num_machines 1
