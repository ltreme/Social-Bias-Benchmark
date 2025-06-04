#!/bin/bash

accelerate launch app/main.py \
    2>&1 | tee "$LOGFILE" | send_to_telemetry
