#!/bin/bash
# P0: Fun-ASR native diarization
python -m alimeeting_diarization_bench.run \
    --model fun_asr \
    --window-size 30 \
    --segments-per-meeting 3 \
    "$@"
