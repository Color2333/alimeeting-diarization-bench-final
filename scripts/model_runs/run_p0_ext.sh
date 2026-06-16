#!/bin/bash
# P0 extended: paraformer-v2 + gpt-4o-audio-preview
python -m alimeeting_diarization_bench.run \
    --model paraformer_v2 gpt4o_audio \
    --window-size 30 \
    --segments-per-meeting 1 \
    "$@"
