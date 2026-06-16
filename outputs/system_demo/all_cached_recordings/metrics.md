# Realtime Diarization System Metrics

- Execution mode: `offline_replay_existing_fast_slow_outputs_with_rule_writeback`
- Run scope: `all_cached_recordings`
- Evaluation status: `scored_with_cached_reference`
- Selector validation status: `weak_dev_gain_not_robust`
- Recording: `None`
- Recordings processed: `8`
- Windows processed: `120`
- Cached window coverage: `120/120` (`100.0%`)
- API calls: DeepSeek `0`, Qwen `0`, Omni `0`

| Metric | Value |
|---|---:|
| Fast DER | 28.56% |
| Final DER | 16.49% |
| DER delta vs fast | 12.07 pp |
| Best baseline | slow_base / 16.88% |
| DER delta vs best baseline | 0.39 pp |
| Beats best baseline | True |
| Beats all baselines | True (5/5) |
| Final Miss | 5.26% |
| Final FA | 6.39% |
| Final Confusion | 4.84% |
| Correction rows | 2664 |
| Accepted writebacks | 95 |
| Accepted window corrections | 114 |
| Guard fallback windows | 1 |
| Blocked/deferred/quarantined | 2569 |
| First output latency proxy avg / P95 | 0.383s / 0.444s |
| Rule writeback latency proxy avg / P95 | 24.647s / 28.330s |
| Processed audio seconds | 3600.0s |
| Total CLI wall time | 3.079s |
| Offline replay RTF | 0.000855 |

## Reading

- DER/Miss/FA/Conf are scored only when cached AliMeeting reference segments are available.
- Latency values are proxies from existing model runs, not fresh online inference timings.
- Offline replay RTF is CLI wall time divided by processed cached-window audio seconds.
- The final timeline uses conservative rule recover writeback; guard/quarantine rows do not enter the timeline.
- This run performs zero live LLM/API calls.

## Selector Validation

| Check | Value |
|---|---:|
| Status | weak_dev_gain_not_robust |
| Boundary | development_pool_validation_not_true_heldout |
| Fixed delta vs slow | 0.29 pp |
| Bootstrap P(beats slow) | 63.3% |
| Bootstrap delta CI low/high | 0.00 pp / 0.87 pp |
| Holdout positive splits | 1/8 |

## Selector Policy Search

| Check | Value |
|---|---:|
| Status | no_robust_candidate_found |
| Best policy | if_guard_count_>=_19_and_fast_spk_>=_slow_spk_then_fast_base_else_slow_base |
| Best delta vs slow | 0.29 pp |
| Holdout weighted delta vs slow | -0.27 pp |
| Holdout positive splits | 0/8 |

## Slow Sanitization Search

| Check | Value |
|---|---:|
| Status | no_robust_sanitizer_found |
| Policy set / candidates | core / 14 |
| Best policy | slow |
| Best delta vs slow | 0.00 pp |
| Bootstrap P(beats slow) | 0.0% |
| Holdout weighted delta vs slow | -0.02 pp |
| Holdout positive splits | 0/8 |

## Recording Summary

| Recording | Windows | Fast DER | Final DER | Delta |
|---|---:|---:|---:|---:|
| R8001_M8004 | 15 | 48.35% | 17.92% | 30.43 pp |
| R8003_M8001 | 15 | 45.38% | 35.89% | 9.49 pp |
| R8007_M8010 | 15 | 35.31% | 24.35% | 10.97 pp |
| R8007_M8011 | 15 | 30.17% | 15.88% | 14.29 pp |
| R8008_M8013 | 15 | 28.67% | 16.67% | 12.00 pp |
| R8009_M8018 | 15 | 14.54% | 10.30% | 4.24 pp |
| R8009_M8019 | 15 | 12.77% | 5.65% | 7.12 pp |
| R8009_M8020 | 15 | 13.31% | 5.28% | 8.03 pp |
