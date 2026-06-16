# Runtime-Safe LLM Guard Latency Breakdown

| Windows | Patches | Avg call | Median call | P95 call | Max call | Avg correction | P95 correction | Avg tokens/window |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 104 | 1917 | 20.27s | 19.28s | 35.35s | 48.47s | 44.92s | 59.99s | 7961 |

## By Window Decision

| Decision | Windows | Patches | Avg patches/window | Avg call | P95 call | Avg correction | P95 correction |
|---|---:|---:|---:|---:|---:|---:|---:|
| quarantine | 96 | 1740 | 18.12 | 19.61s | 33.16s | 44.25s | 57.81s |
| review | 8 | 177 | 22.12 | 28.26s | 41.47s | 52.91s | 66.11s |

## By Patch Count Bucket

| Patch bucket | Windows | Patches | Avg patches/window | Avg call | P95 call | Avg correction | P95 correction |
|---|---:|---:|---:|---:|---:|---:|---:|
| 02_3-5 | 17 | 62 | 3.65 | 9.60s | 16.72s | 34.25s | 41.37s |
| 03_6-15 | 29 | 331 | 11.41 | 15.99s | 24.15s | 40.64s | 48.80s |
| 04_>15 | 58 | 1524 | 26.28 | 25.54s | 36.94s | 50.18s | 61.59s |

## Slowest Windows

| Window | Decision | Patches | Call | Correction delay | Tokens | Reason |
|---|---|---:|---:|---:|---:|---|
| R8007_M8010:30:0 | quarantine | 45 | 48.47s | 73.11s | 17217 | proxy_abnormal_speech_too_long |
| R8007_M8010:30:6 | review | 40 | 44.56s | 69.20s | 17354 | proxy_risk_window |
| R8007_M8010:30:3 | quarantine | 42 | 39.72s | 64.37s | 16004 | multiple_proxy_flags_and_speaker_count_mismatch |
| R8009_M8020:30:12 | quarantine | 37 | 36.45s | 61.09s | 15494 | slow_pred_speech_too_long_proxy_risk |
| R8003_M8001:30:12 | review | 23 | 35.73s | 60.38s | 10507 | slow_proxy_risk_flagged |
| R8003_M8001:30:2 | quarantine | 30 | 35.52s | 60.16s | 12035 | pred_speech_too_long_proxy_flag |
| R8007_M8010:30:2 | quarantine | 32 | 34.40s | 59.05s | 12539 | deployable_proxy_flags_and_speaker_count_mismatch |
| R8003_M8001:30:10 | quarantine | 33 | 32.75s | 57.39s | 13073 | proxy_risk_long_speech |

## Reading

- Correction delay here is estimated as current rule-writeback average delay plus each measured LLM call time.
- The existing safety summary keeps the conservative P95 contract as slow-layer P95 plus LLM-call P95.
- Patch count is a useful but incomplete latency driver; model-side generation and token count still dominate some outliers.
