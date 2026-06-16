# Split LLM Run Summary

| Parent window | Patches | Original call | Split calls | Split max call | Token multiplier | Reduction |
|---|---:|---:|---:|---:|---:|---:|
| R8009_M8020:30:12 | 37 | 36.45s | 2 | 41.33s | 1.29x | -13.4% |
| R8003_M8001:30:12 | 23 | 35.73s | 2 | 44.00s | 1.52x | -23.1% |

## Summary

| Parents | Patches | Split calls | Original avg | Split parent avg max | Original max | Split max | Token multiplier | Harmful accepts |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 60 | 4 | 36.09s | 42.67s | 36.45s | 44.00s | 1.38x | 0 |

## Run Batches

| Run | Calls | Successful calls | Wall | Workers | Harmful accepts |
|---|---:|---:|---:|---:|---:|
| qwen36_flash_split20_top4_5_parallel_summary | 4 | 4 | 44.02s | 4 | 0 |

## Reading

- `Split max call` is the parent-window wall-clock estimate if that parent's subcalls run concurrently.
- Batch `Wall` is the measured wall-clock for that script invocation, including local scheduling and API round trip.
- If multiple batches are provided, their walls are measured separately and should not be treated as one all-at-once topN wall-clock.
