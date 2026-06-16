# System Selector Policy Search

- Runtime contract: `system_selector_policy_search_no_live_calls_runtime_features_only`
- Status: `no_robust_candidate_found`
- Best full policy: `if_guard_count_>=_19_and_fast_spk_>=_slow_spk_then_fast_base_else_slow_base`
- Best full DER: `16.59%` vs Slow `16.88%`
- Holdout positive splits: `0/8`
- Holdout weighted delta vs Slow: `-0.27pp`

## Top Policies

| Rank | Policy | Final DER | Slow DER | Delta | Choices |
|---:|---|---:|---:|---:|---|
| 1 | `if_guard_count_>=_19_and_fast_spk_>=_slow_spk_then_fast_base_else_slow_base` | 16.59% | 16.88% | 0.29pp | `{"fast_base": 1, "slow_base": 119}` |
| 2 | `if_guard_count_>=_9.5_and_fast_spk_>=_slow_spk_then_fast_base_else_slow_base` | 16.59% | 16.88% | 0.29pp | `{"fast_base": 1, "slow_base": 119}` |
| 3 | `if_guard_count_>=_19_then_fast_base_else_slow_base` | 16.75% | 16.88% | 0.13pp | `{"fast_base": 2, "slow_base": 118}` |
| 4 | `if_guard_count_>=_19_then_rule_recover_matched_label_else_slow_base` | 16.75% | 16.88% | 0.13pp | `{"rule_recover_matched_label": 2, "slow_base": 118}` |
| 5 | `if_guard_count_>=_19_then_rule_recover_policy_sweep_best_else_slow_base` | 16.75% | 16.88% | 0.13pp | `{"rule_recover_policy_sweep_best": 2, "slow_base": 118}` |
| 6 | `if_guard_count_>=_19_then_rule_recover_uncovered_only_else_slow_base` | 16.75% | 16.88% | 0.13pp | `{"rule_recover_uncovered_only": 2, "slow_base": 118}` |
| 7 | `if_guard_count_>=_9.5_then_fast_base_else_slow_base` | 16.75% | 16.88% | 0.13pp | `{"fast_base": 2, "slow_base": 118}` |
| 8 | `if_guard_count_>=_9.5_then_rule_recover_matched_label_else_slow_base` | 16.75% | 16.88% | 0.13pp | `{"rule_recover_matched_label": 2, "slow_base": 118}` |
| 9 | `if_guard_count_>=_9.5_then_rule_recover_policy_sweep_best_else_slow_base` | 16.75% | 16.88% | 0.13pp | `{"rule_recover_policy_sweep_best": 2, "slow_base": 118}` |
| 10 | `if_guard_count_>=_9.5_then_rule_recover_uncovered_only_else_slow_base` | 16.75% | 16.88% | 0.13pp | `{"rule_recover_uncovered_only": 2, "slow_base": 118}` |
| 11 | `if_audio_max_speech_ratio_>=_0.6387_then_rule_recover_policy_sweep_best_else_slow_base` | 16.76% | 16.88% | 0.12pp | `{"rule_recover_policy_sweep_best": 3, "slow_base": 117}` |
| 12 | `if_audio_max_speech_ratio_>=_0.6387_then_rule_recover_uncovered_only_else_slow_base` | 16.76% | 16.88% | 0.12pp | `{"rule_recover_uncovered_only": 3, "slow_base": 117}` |
| 13 | `if_audio_max_speech_sec_>=_19.16_then_rule_recover_policy_sweep_best_else_slow_base` | 16.76% | 16.88% | 0.12pp | `{"rule_recover_policy_sweep_best": 3, "slow_base": 117}` |
| 14 | `if_audio_max_speech_sec_>=_19.16_then_rule_recover_uncovered_only_else_slow_base` | 16.76% | 16.88% | 0.12pp | `{"rule_recover_uncovered_only": 3, "slow_base": 117}` |
| 15 | `if_slow_segments_<=_5.5_then_rule_recover_matched_label_else_slow_base` | 16.77% | 16.88% | 0.11pp | `{"rule_recover_matched_label": 9, "slow_base": 111}` |
| 16 | `if_slow_segments_<=_5_then_rule_recover_matched_label_else_slow_base` | 16.77% | 16.88% | 0.11pp | `{"rule_recover_matched_label": 9, "slow_base": 111}` |
| 17 | `if_slow_segments_<=_5.5_then_rule_recover_policy_sweep_best_else_slow_base` | 16.78% | 16.88% | 0.10pp | `{"rule_recover_policy_sweep_best": 9, "slow_base": 111}` |
| 18 | `if_slow_segments_<=_5.5_then_rule_recover_uncovered_only_else_slow_base` | 16.78% | 16.88% | 0.10pp | `{"rule_recover_uncovered_only": 9, "slow_base": 111}` |
| 19 | `if_slow_segments_<=_5_then_rule_recover_policy_sweep_best_else_slow_base` | 16.78% | 16.88% | 0.10pp | `{"rule_recover_policy_sweep_best": 9, "slow_base": 111}` |
| 20 | `if_slow_segments_<=_5_then_rule_recover_uncovered_only_else_slow_base` | 16.78% | 16.88% | 0.10pp | `{"rule_recover_uncovered_only": 9, "slow_base": 111}` |

## Reading

- Policies use only deployable Fast/Slow prediction features and gate counts.
- DER is used only after the policy chooses a timeline variant.
- If holdout is weak, the policy should not be promoted beyond development-pool evidence.
