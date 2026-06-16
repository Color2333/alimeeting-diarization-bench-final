#!/bin/bash
# Round 2: 4 prompt variants for omni-plus
python -m alimeeting_diarization_bench.run \
    --model omni_plus \
    --window-sizes 30 60 \
    --segments-per-meeting 3 \
    --variants basic srt_format structured xml_format \
    "$@"
