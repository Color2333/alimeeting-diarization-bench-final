# Split20 Live Top1 Comparison

| Window | Patches | Original call | Split calls | Parallel split call | Sequential script time | Token multiplier | Harmful accepts | Parent override |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| R8007_M8010:30:0 | 45 | 48.47s | 3 | 24.49s | 57.88s | 1.14x | 0 | True |

## Reading

- This is a real `deepseek-v4-flash` split20 call on the slowest observed 104w parent window.
- The current script called sub-batches sequentially; `parallel split call` is the deployable wall-clock estimate if subcalls run concurrently.
- Parent-window quarantine override is applied after merging subcalls, so any subcall quarantine blocks accepts from sibling review subcalls.
