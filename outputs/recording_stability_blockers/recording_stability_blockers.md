# Recording Stability Blocker Diagnosis

- Runtime contract: `analysis_only_recording_stability_blocker_diagnosis_no_live_calls`
- Status: `candidate_pool_exhausted_for_non_positive_recordings`
- Non-positive recordings: `3/8`
- Non-positive candidate-pool oracle gain: `0.0000pp`
- Global clipped-candidate oracle gap: `0.0128pp`

## Non-Positive Recordings

| Recording | Final DER | Baseline DER | Oracle DER | Delta vs baseline | Oracle gain vs baseline | Better windows | Sources | Oracle variants |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `R8001_M8004` | 17.92% | 17.92% | 17.92% | 0.0000pp | 0.0000pp | 0 | `{"slow": 15}` | `{"slow_base": 15}` |
| `R8008_M8013` | 16.67% | 16.67% | 16.67% | 0.0000pp | 0.0000pp | 0 | `{"slow": 15}` | `{"slow_base": 15}` |
| `R8009_M8020` | 5.28% | 5.28% | 5.28% | 0.0000pp | 0.0000pp | 0 | `{"slow": 15}` | `{"slow_base": 15}` |

## Remaining Search Surface

| Search | Status | Current positive | Best positive | Best delta | Negatives |
|---|---|---:|---:|---:|---:|
| `current_window_only` | `no_deployable_recording_balanced_candidate_found` | 5 | 5 | 0.0029pp | 0 |
| `current_plus_previous_window` | `no_deployable_recording_balanced_candidate_found` | 5 | 5 | 0.0029pp | 0 |

## GT-Filtered External Candidate Surface

- Status: `external_candidate_surface_not_deployable`
- Best delta vs current: `0.0002pp`
- Best positive recordings: `7/8`
- Best source stale GT-mismatch windows: `0`
- Oracle gain vs current: `0.0110pp`

## Reading

- If non-positive recordings have near-zero clipped-candidate oracle gain, existing Fast/Slow/rule variants cannot make recording-level robustness true.
- The next useful optimization should create new correction candidates or stronger speaker/activity evidence, rather than only retuning current thresholds.
