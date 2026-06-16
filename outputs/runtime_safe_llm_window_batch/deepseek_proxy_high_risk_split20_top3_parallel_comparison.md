# Split20 Live Top3 Parallel Comparison

| Parent window | Patches | Original call | Split calls | Split max call | Token multiplier | Reduction |
|---|---:|---:|---:|---:|---:|---:|
| R8007_M8010:30:0 | 45 | 48.47s | 3 | 22.14s | 1.08x | 54.3% |
| R8007_M8010:30:6 | 40 | 44.56s | 2 | 23.30s | 0.95x | 47.7% |
| R8007_M8010:30:3 | 42 | 39.72s | 3 | 28.99s | 1.28x | 27.0% |

## Summary

| Parents | Patches | Workers | Measured wall | Original max | Split max call | Token multiplier | Harmful accepts |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 127 | 8 | 29.01s | 48.47s | 28.99s | 1.10x | 0 |

## Reading

- These are real concurrent split20 calls on the three slowest observed 104w parent windows.
- `Measured wall` includes local scheduling and API round-trip overhead for all eight subcalls.
- Parent-window quarantine override is applied after subcall merge.
