# Split20 Live Top3 Comparison

| Parent window | Patches | Original call | Split calls | Parallel split call | Sequential script time | Token multiplier |
|---|---:|---:|---:|---:|---:|---:|
| R8007_M8010:30:0 | 45 | 48.47s | 3 | 24.49s | 57.88s | 1.14x |
| R8007_M8010:30:6 | 40 | 44.56s | 2 | 27.80s | 52.76s | 1.02x |
| R8007_M8010:30:3 | 42 | 39.72s | 3 | 23.05s | 54.61s | 1.21x |

## Summary

| Parents | Patches | Original avg call | Parallel split avg call | Original max | Split max | Token multiplier | Harmful accepts |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 127 | 44.25s | 25.11s | 48.47s | 27.80s | 1.12x | 0 |

## Reading

- These are real split20 calls on the three slowest observed 104w parent windows.
- Current script execution is sequential; parallel split call is the deployable wall-clock estimate if subcalls are dispatched concurrently.
- Parent-window quarantine override is applied for safety after subcall merge.
