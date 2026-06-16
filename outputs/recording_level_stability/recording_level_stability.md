# Recording-Level Stability Audit

- Runtime contract: `recording_level_stability_no_live_calls_no_new_model_inference`
- Status: `weak_recording_level_gain_not_robust`
- Baseline: `slow_base`
- Recordings: `8`
- Positive recordings: `5/8`
- Mean final DER: `16.49%`
- Mean baseline DER: `16.88%`
- Mean delta: `0.387pp`
- Recording bootstrap P(beats baseline): `99.9%`
- Recording bootstrap delta CI: `0.019pp` to `0.969pp`

## Per Recording

| Recording | Windows | Final DER | Baseline DER | Delta | Beats | Sources |
|---|---:|---:|---:|---:|---:|---|
| `R8001_M8004` | 15 | 17.92% | 17.92% | 0.000pp | False | `{"slow": 15}` |
| `R8003_M8001` | 15 | 35.89% | 38.21% | 2.325pp | True | `{"fast_guard_fallback": 1, "slow": 14}` |
| `R8007_M8010` | 15 | 24.35% | 24.38% | 0.035pp | True | `{"recording_context_fast_overlay": 1, "slow": 14}` |
| `R8007_M8011` | 15 | 15.88% | 16.47% | 0.589pp | True | `{"rare_audio_rule_recover": 1, "rare_short_slow_rule_recover": 1, "slow": 13}` |
| `R8008_M8013` | 15 | 16.67% | 16.67% | 0.000pp | False | `{"slow": 15}` |
| `R8009_M8018` | 15 | 10.30% | 10.34% | 0.033pp | True | `{"recording_balanced_fast_overlay": 1, "slow": 14}` |
| `R8009_M8019` | 15 | 5.65% | 5.77% | 0.117pp | True | `{"rare_short_slow_rule_recover": 1, "slow": 14}` |
| `R8009_M8020` | 15 | 5.28% | 5.28% | 0.000pp | False | `{"slow": 15}` |

## Reading

- This is stricter than window bootstrap because each sample resamples whole recordings.
- `weak_recording_level_gain_not_robust` means the development-pool mean still improves, but the gain is not stable enough for promotion.
