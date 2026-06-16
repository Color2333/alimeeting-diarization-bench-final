#!/bin/bash
# Round 1: qwen3-asr-flash + qwen3.5-omni-plus baseline
python -m alimeeting_diarization_bench.run \
    --model asr_flash omni_plus \
    --window-sizes 30 60 \
    --segments-per-meeting 3 \
    "$@"
