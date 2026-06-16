# Recording-Balanced Overlay Search

- Runtime contract: `recording_balanced_overlay_search_no_live_calls_runtime_features_only`
- Status: `no_deployable_recording_balanced_candidate_found`
- Current positive recordings: `5/8`
- Best positive recordings: `5/8`
- Best policy: `if_align_slow_segment_<=_4_AND_prev_audio_dynamic_range_db_>=_21.35_then_rule_recover_policy_sweep_best_else_current_final`
- Best final DER: `16.49%`
- Delta vs current final: `0.003pp`
- Negative recordings vs clipped Slow: `0`

## Top Policies

| Rank | Policy | Final DER | Delta vs current | Positive recs | Negative recs | Selected | Wins/Losses |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `if_align_slow_segment_<=_4_AND_prev_audio_dynamic_range_db_>=_21.35_then_rule_recover_policy_sweep_best_else_current_final` | 16.49% | 0.003pp | 5 | 0 | 1 | 1/0 |
| 2 | `if_align_slow_segment_<=_4_AND_prev_audio_dynamic_range_db_>=_21.35_then_rule_recover_uncovered_only_else_current_final` | 16.49% | 0.003pp | 5 | 0 | 1 | 1/0 |
| 3 | `if_align_slow_segment_<=_4_AND_prev_audio_max_speech_sec_>=_18.25_then_rule_recover_policy_sweep_best_else_current_final` | 16.49% | 0.003pp | 5 | 0 | 2 | 1/0 |
| 4 | `if_align_slow_segment_<=_4_AND_prev_audio_max_speech_sec_>=_18.25_then_rule_recover_uncovered_only_else_current_final` | 16.49% | 0.003pp | 5 | 0 | 2 | 1/0 |
| 5 | `if_align_slow_segment_<=_3_AND_boundary_fix_or_relabel_<=_1_then_fast_base_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 6 | `if_align_slow_segment_<=_3_AND_boundary_fix_or_relabel_<=_1_then_rule_recover_matched_label_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 7 | `if_align_slow_segment_<=_3_AND_boundary_fix_or_relabel_<=_1_then_rule_recover_policy_sweep_best_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 8 | `if_align_slow_segment_<=_3_AND_boundary_fix_or_relabel_<=_1_then_rule_recover_uncovered_only_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 9 | `if_align_slow_segment_<=_4_AND_audio_channel_activity_mean_>=_3.6204_then_fast_base_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 10 | `if_align_slow_segment_<=_4_AND_audio_channel_activity_mean_>=_3.6204_then_rule_recover_matched_label_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 11 | `if_align_slow_segment_<=_4_AND_audio_channel_activity_mean_>=_3.6204_then_rule_recover_policy_sweep_best_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 12 | `if_align_slow_segment_<=_4_AND_audio_channel_activity_mean_>=_3.6204_then_rule_recover_uncovered_only_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 13 | `if_align_slow_segment_>=_18_AND_keep_fast_supported_>=_6_then_fast_base_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 14 | `if_align_slow_segment_>=_18_AND_keep_fast_supported_>=_6_then_rule_recover_matched_label_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 15 | `if_align_slow_segment_>=_18_AND_keep_fast_supported_>=_6_then_rule_recover_policy_sweep_best_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 16 | `if_align_slow_segment_>=_18_AND_keep_fast_supported_>=_6_then_rule_recover_uncovered_only_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 17 | `if_audio_p50_db_>=_-36.6753_AND_prev_audio_dynamic_range_db_<=_10.1179_then_fast_base_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 18 | `if_audio_p50_db_>=_-36.6753_AND_prev_audio_dynamic_range_db_<=_10.1179_then_rule_recover_matched_label_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 19 | `if_audio_p50_db_>=_-36.6753_AND_prev_audio_dynamic_range_db_<=_10.1179_then_rule_recover_policy_sweep_best_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |
| 20 | `if_audio_p50_db_>=_-36.6753_AND_prev_audio_dynamic_range_db_<=_10.1179_then_rule_recover_uncovered_only_else_current_final` | 16.49% | 0.000pp | 5 | 0 | 1 | 0/0 |

## Reading

- This search optimizes recording-level stability over the current final runtime output.
- DER is used only after runtime-safe condition materialization for offline ranking.
- A deployable candidate must improve the recording-positive count without hurting the current final DER or creating negative recordings.
