# Runtime Overlay Contribution Audit

- Runtime contract: `runtime_overlay_contribution_audit_no_live_calls_clipped_baseline_reference`
- Status: `pass`
- Overlay windows: `6`
- Contribution vs clipped Slow: `0.3873pp`
- Final margin vs clipped Slow: `0.3873pp`
- Negative overlay windows: `0`

## By Source

| Source | Windows | Contribution | Avg Delta | Negative Windows | Recordings |
|---|---:|---:|---:|---:|---|
| `fast_guard_fallback` | 1 | 0.2907pp | 34.880pp | 0 | `R8003_M8001` |
| `rare_audio_rule_recover` | 1 | 0.0708pp | 8.500pp | 0 | `R8007_M8011` |
| `rare_short_slow_rule_recover` | 2 | 0.0173pp | 1.040pp | 0 | `R8007_M8011,R8009_M8019` |
| `recording_balanced_fast_overlay` | 1 | 0.0041pp | 0.490pp | 0 | `R8009_M8018` |
| `recording_context_fast_overlay` | 1 | 0.0044pp | 0.530pp | 0 | `R8007_M8010` |
| `slow` | 114 | 0.0000pp | 0.000pp | 0 | `R8001_M8004,R8003_M8001,R8007_M8010,R8007_M8011,R8008_M8013,R8009_M8018,R8009_M8019,R8009_M8020` |

## Overlay Windows

| Window | Source | Recording | Final DER | Slow DER | Delta vs Slow | Fast DER |
|---|---|---|---:|---:|---:|---:|
| `R8003_M8001:30:9` | `fast_guard_fallback` | `R8003_M8001` | 324.59% | 359.47% | 34.880pp | 324.59% |
| `R8007_M8010:30:3` | `recording_context_fast_overlay` | `R8007_M8010` | 29.36% | 29.89% | 0.530pp | 29.36% |
| `R8007_M8011:30:0` | `rare_short_slow_rule_recover` | `R8007_M8011` | 2.92% | 3.25% | 0.330pp | 2.92% |
| `R8007_M8011:30:8` | `rare_audio_rule_recover` | `R8007_M8011` | 34.16% | 42.66% | 8.500pp | 36.75% |
| `R8009_M8018:30:12` | `recording_balanced_fast_overlay` | `R8009_M8018` | 16.08% | 16.57% | 0.490pp | 16.08% |
| `R8009_M8019:30:12` | `rare_short_slow_rule_recover` | `R8009_M8019` | 1.58% | 3.33% | 1.750pp | 12.92% |

## Reading

- Contributions are measured against the clipped Slow baseline on the same windows.
- A pass means every active overlay source has non-negative aggregate contribution and no window-level regression versus clipped Slow.
