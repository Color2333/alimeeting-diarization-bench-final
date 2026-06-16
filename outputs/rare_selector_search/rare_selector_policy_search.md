# Rare Selector Overlay Search

- Runtime contract: `rare_selector_overlay_no_live_calls_runtime_features_only`
- Status: `weak_dev_gain_not_robust`
- Windows: `120`
- Best policy: `if_audio_speech_sec_>=_18.605_then_rule_recover_uncovered_only_else_default_guarded_selector`
- Final DER: `16.52%` vs base `16.59%`
- Delta vs base: `0.071pp`
- Selected windows: `1`
- Bootstrap P(beats base): `62.2%`
- Holdout positive splits vs base: `0/8`
- Holdout weighted delta vs base: `-0.498pp`
- Runtime stacked policy DER: `16.50%` vs base `16.59%`
- Runtime stacked delta vs base: `0.088pp`
- Runtime stacked selected windows: `3`
- Runtime stacked bootstrap P(beats base): `94.2%`

## Top Policies

| Rank | Policy | Final DER | Base DER | Delta | Selected | Wins/Losses |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `if_audio_speech_sec_>=_18.605_then_rule_recover_uncovered_only_else_default_guarded_selector` | 16.52% | 16.59% | 0.071pp | 1 | 1/0 |
| 2 | `if_audio_speech_sec_>=_18.605_then_rule_recover_matched_label_else_default_guarded_selector` | 16.52% | 16.59% | 0.071pp | 1 | 1/0 |
| 3 | `if_audio_speech_sec_>=_18.605_then_rule_recover_policy_sweep_best_else_default_guarded_selector` | 16.52% | 16.59% | 0.071pp | 1 | 1/0 |
| 4 | `if_audio_speech_sec_>=_15.92_AND_seg_diff_<=_-7_then_rule_recover_matched_label_else_default_guarded_selector` | 16.54% | 16.59% | 0.054pp | 2 | 1/1 |
| 5 | `if_audio_speech_sec_>=_15.92_AND_seg_diff_<=_-7_then_rule_recover_uncovered_only_else_default_guarded_selector` | 16.54% | 16.59% | 0.054pp | 2 | 1/1 |
| 6 | `if_audio_speech_sec_>=_15.92_AND_seg_diff_<=_-7_then_rule_recover_policy_sweep_best_else_default_guarded_selector` | 16.54% | 16.59% | 0.054pp | 2 | 1/1 |
| 7 | `if_audio_speech_sec_>=_18.605_then_fast_base_else_default_guarded_selector` | 16.54% | 16.59% | 0.049pp | 1 | 1/0 |
| 8 | `if_audio_speech_sec_>=_17.4_then_rule_recover_uncovered_only_else_default_guarded_selector` | 16.55% | 16.59% | 0.045pp | 2 | 1/1 |
| 9 | `if_audio_speech_sec_>=_17.4_then_rule_recover_matched_label_else_default_guarded_selector` | 16.55% | 16.59% | 0.045pp | 2 | 1/1 |
| 10 | `if_audio_speech_sec_>=_17.4_then_rule_recover_policy_sweep_best_else_default_guarded_selector` | 16.55% | 16.59% | 0.045pp | 2 | 1/1 |
| 11 | `if_fast_audio_speech_overrun_sec_<=_9.6_AND_seg_diff_<=_-8_then_rule_recover_uncovered_only_else_default_guarded_selector` | 16.56% | 16.59% | 0.035pp | 3 | 2/1 |
| 12 | `if_fast_audio_speech_overrun_sec_<=_9.6_AND_seg_diff_<=_-8_then_rule_recover_policy_sweep_best_else_default_guarded_selector` | 16.56% | 16.59% | 0.035pp | 3 | 2/1 |
| 13 | `if_fast_audio_speech_overrun_sec_<=_7.4_AND_seg_diff_<=_-8_then_rule_recover_uncovered_only_else_default_guarded_selector` | 16.56% | 16.59% | 0.032pp | 2 | 1/1 |
| 14 | `if_fast_audio_speech_overrun_sec_<=_7.4_AND_seg_diff_<=_-8_then_rule_recover_policy_sweep_best_else_default_guarded_selector` | 16.56% | 16.59% | 0.032pp | 2 | 1/1 |
| 15 | `if_fast_audio_speech_overrun_sec_<=_7.4_AND_seg_diff_<=_-8_then_rule_recover_matched_label_else_default_guarded_selector` | 16.56% | 16.59% | 0.031pp | 2 | 1/1 |
| 16 | `if_audio_channel_activity_mean_>=_3.7145_AND_slow_audio_speech_ratio_<=_1.98478_then_rule_recover_uncovered_only_else_default_guarded_selector` | 16.57% | 16.59% | 0.025pp | 2 | 1/1 |
| 17 | `if_audio_channel_activity_mean_>=_3.7145_AND_slow_audio_speech_ratio_<=_1.98478_then_rule_recover_matched_label_else_default_guarded_selector` | 16.57% | 16.59% | 0.025pp | 2 | 1/1 |
| 18 | `if_audio_channel_activity_mean_>=_3.7145_AND_slow_audio_speech_ratio_<=_1.98478_then_rule_recover_policy_sweep_best_else_default_guarded_selector` | 16.57% | 16.59% | 0.025pp | 2 | 1/1 |
| 19 | `if_audio_speech_sec_>=_17.4_then_fast_base_else_default_guarded_selector` | 16.57% | 16.59% | 0.023pp | 2 | 1/1 |
| 20 | `if_slow_segments_<=_3_then_rule_recover_uncovered_only_else_default_guarded_selector` | 16.57% | 16.59% | 0.017pp | 2 | 2/0 |

## Reading

- The overlay uses only runtime-safe prediction, gate, and audio feature artifacts.
- DER is used only after policy materialization for offline ranking and validation.
- Weak holdout means this is a development-pool optimization, not a robust generalization claim.
