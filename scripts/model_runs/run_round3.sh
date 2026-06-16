#!/bin/bash
# Round 3: Two-stage agent (asr-flash -> omni-plus with transcript reference)
python -m alimeeting_diarization_bench.run \
    --model two_stage_agent \
    --window-sizes 30 60 \
    --segments-per-meeting 3 \
    --variants baseline agent_guided agent_spkhint \
    "$@"
