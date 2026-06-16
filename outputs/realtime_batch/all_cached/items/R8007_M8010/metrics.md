# Realtime Diarization System Metrics

- Execution mode: `offline_replay_existing_fast_slow_outputs_with_rule_writeback`
- Run scope: `single_recording_or_audio`
- Evaluation status: `scored_with_cached_reference`
- Selector validation status: `weak_dev_gain_not_robust`
- Recording: `R8007_M8010`
- Recordings processed: `1`
- Windows processed: `15`
- Cached window coverage: `15/120` (`12.5%`)
- API calls: DeepSeek `0`, Qwen `0`, Omni `0`

| Metric | Value |
|---|---:|
| Fast DER | 35.31% |
| Final DER | 24.35% |
| DER delta vs fast | 10.97 pp |
| Best baseline | slow_base / 24.38% |
| DER delta vs best baseline | 0.03 pp |
| Beats best baseline | True |
| Beats all baselines | True (5/5) |
| Final Miss | 10.82% |
| Final FA | 3.63% |
| Final Confusion | 9.90% |
| Correction rows | 544 |
| Accepted writebacks | 6 |
| Accepted window corrections | 14 |
| Guard fallback windows | 0 |
| Blocked/deferred/quarantined | 538 |
| First output latency proxy avg / P95 | 0.366s / 0.380s |
| Rule writeback latency proxy avg / P95 | 23.923s / 25.514s |
| Processed audio seconds | 450.0s |
| Total CLI wall time | 0.491s |
| Offline replay RTF | 0.001092 |

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
| R8007_M8010 | 15 | 35.31% | 24.35% | 10.97 pp |
