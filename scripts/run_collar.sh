#!/bin/bash
# Collar comparison: Re-calculate DER with collar=0.0, 0.25, 0.5
python -m alimeeting_diarization_bench.collar_comparison \
    --collars 0.0 0.25 0.5 \
    "$@"
