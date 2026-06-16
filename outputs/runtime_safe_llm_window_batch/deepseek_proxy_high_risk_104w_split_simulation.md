# Runtime-Safe LLM Guard Split Simulation

This is an offline latency planning model. It estimates parallel sub-batching from measured 104-window calls; it is not a live-call result.

## Fitted Model

| Relationship | Intercept | Slope |
|---|---:|---:|
| total_tokens ~ patch_count | 1699.85 | 339.67 |
| call_seconds ~ total_tokens | 4.02 | 0.002042 |

## Policy Summary

| Max patches/subcall | Split windows | Calls | Added calls | Avg call | P95 call | Max call | Avg correction | P95 correction | Token multiplier |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 40 | 147 | 43 | 16.58s | 21.36s | 23.47s | 41.23s | 46.01s | 1.12x |
| 15 | 58 | 178 | 74 | 14.98s | 18.05s | 19.65s | 39.62s | 42.69s | 1.18x |
| 12 | 70 | 209 | 105 | 13.86s | 16.19s | 17.15s | 38.51s | 40.84s | 1.25x |
| 10 | 76 | 239 | 135 | 13.10s | 15.08s | 16.23s | 37.75s | 39.73s | 1.31x |
| 8 | 82 | 286 | 182 | 12.24s | 13.65s | 14.25s | 36.89s | 38.29s | 1.40x |

## Recommended Next Test

- Validate `max_patches_per_call=20` with live calls on the slowest windows first: estimated P95 call 21.36s vs observed 35.35s, added calls 43, token multiplier 1.12x.
- Treat the numbers as a routing budget, not as claimed model performance, until the split prompt is actually called.
