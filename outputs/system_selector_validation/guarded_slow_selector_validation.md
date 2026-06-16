# Guarded Slow Selector Validation

- Runtime contract: `guarded_slow_selector_validation_no_live_calls_runtime_features_only`
- Status: `weak_dev_gain_not_robust`
- Fixed policy: `slow_guarded_fast_fallback_speaker_count_safe` with threshold `1`
- Windows: `120`
- Final DER: `16.59%`
- Slow baseline DER: `16.88%`
- Delta vs slow: `0.29pp`
- Beats slow: `True`
- Fast fallback windows: `1`
- Fallback blocked by speaker count: `1`
- Bootstrap P(beats slow): `63.3%`
- Bootstrap delta CI: `0.00pp` to `0.87pp`

## Threshold Scan

| Threshold | Final DER | Slow DER | Delta | Fast fallback windows | Speaker blocks | Beats slow |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 16.59% | 16.88% | 0.29pp | 1 | 1 | True |
| 2 | 16.59% | 16.88% | 0.29pp | 1 | 1 | True |
| 3 | 16.59% | 16.88% | 0.29pp | 1 | 1 | True |
| 5 | 16.59% | 16.88% | 0.29pp | 1 | 1 | True |
| 10 | 16.59% | 16.88% | 0.29pp | 1 | 1 | True |
| 15 | 16.59% | 16.88% | 0.29pp | 1 | 1 | True |
| 20 | 16.88% | 16.88% | 0.00pp | 0 | 1 | False |
| 999 | 16.88% | 16.88% | 0.00pp | 0 | 0 | False |

## Recording Holdout

| Heldout recording | Selected threshold | Final DER | Slow DER | Delta | Beats slow |
|---|---:|---:|---:|---:|---:|
| R8001_M8004 | 1 | 17.92% | 17.92% | 0.00pp | False |
| R8003_M8001 | 1 | 35.89% | 38.22% | 2.33pp | True |
| R8007_M8010 | 1 | 24.38% | 24.38% | 0.00pp | False |
| R8007_M8011 | 1 | 16.47% | 16.47% | 0.00pp | False |
| R8008_M8013 | 1 | 16.67% | 16.67% | 0.00pp | False |
| R8009_M8018 | 1 | 10.34% | 10.34% | 0.00pp | False |
| R8009_M8019 | 1 | 5.77% | 5.77% | 0.00pp | False |
| R8009_M8020 | 1 | 5.28% | 5.28% | 0.00pp | False |

## Reading

- Runtime selection uses only `guard_or_quarantine` counts and predicted Fast/Slow speaker counts.
- DER is used only for offline validation and threshold ranking.
- This is still development-pool validation; true held-out recordings remain a separate blocker.
