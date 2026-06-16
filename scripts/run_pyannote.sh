#!/bin/bash
# P1: PyAnnote 3.1 local inference
python -m alimeeting_diarization_bench.run \
    --model pyannote \
    --window-size 30 \
    --segments-per-meeting 1 \
    --use-gpu \
    "$@"
