# External Candidate Surface Search

- Runtime contract: `external_candidate_surface_search_no_live_calls_runtime_features_only`
- Status: `external_candidate_surface_not_deployable`
- Candidate sources: `3`
- Eval-only oracle sources excluded: `0`
- Current positive recordings: `5/8`
- Oracle positive recordings: `8/8`
- Oracle gain vs current: `0.011pp`
- Best policy: `if_boundary_fix_or_relabel_<=_1_AND_prev_audio_channel_activity_mean_>=_3.6101_then_diarizen-large-v2__diarizen-large-v2__spk_none::outputs__diarizen_uv_48__diarizen-large-v2__default__spk_none_else_current_final`
- Best final DER: `16.49%`
- Best delta vs current: `0.000pp`
- Best positive recordings: `7/8`
- Negative recordings: `0`

## Top Policies

| Rank | Policy | Source coverage | Selected | Wins/Losses | Final DER | Delta | Positive recs | Negative recs |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | `if_boundary_fix_or_relabel_<=_1_AND_prev_audio_channel_activity_mean_>=_3.6101_then_diarizen-large-v2__diarizen-large-v2__spk_none::outputs__diarizen_uv_48__diarizen-large-v2__default__spk_none_else_current_final` | 120 | 2 | 2/0 | 16.49% | 0.000pp | 7 | 0 |
| 2 | `if_boundary_fix_or_relabel_<=_1_AND_prev_audio_channel_activity_mean_>=_3.6101_then_diarizen-large-v2__diarizen-large-v2__spk_none_else_current_final` | 120 | 2 | 2/0 | 16.49% | 0.000pp | 7 | 0 |
| 3 | `if_audio_dynamic_range_db_>=_22.3574_then_diarizen-large-v2__diarizen-large-v2__spk_none::outputs__diarizen_uv_48__diarizen-large-v2__default__spk_none_else_current_final` | 120 | 9 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 4 | `if_audio_dynamic_range_db_>=_22.3574_then_diarizen-large-v2__diarizen-large-v2__spk_none_else_current_final` | 120 | 9 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 5 | `if_audio_max_p90_db_<=_-41.4081_AND_prev_audio_max_p90_db_<=_-40.7464_then_diarizen-large-v2__diarizen-large-v2__spk_none::outputs__diarizen_uv_48__diarizen-large-v2__default__spk_none_else_current_final` | 120 | 8 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 6 | `if_audio_max_p90_db_<=_-41.4081_AND_prev_audio_max_p90_db_<=_-40.7464_then_diarizen-large-v2__diarizen-large-v2__spk_none_else_current_final` | 120 | 8 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 7 | `if_audio_p90_db_<=_-45.782_AND_prev_audio_max_p90_db_<=_-40.7464_then_diarizen-large-v2__diarizen-large-v2__spk_none::outputs__diarizen_uv_48__diarizen-large-v2__default__spk_none_else_current_final` | 120 | 9 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 8 | `if_audio_p90_db_<=_-45.782_AND_prev_audio_max_p90_db_<=_-40.7464_then_diarizen-large-v2__diarizen-large-v2__spk_none_else_current_final` | 120 | 9 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 9 | `if_audio_p90_db_<=_-45.9942_AND_prev_audio_max_p90_db_<=_-40.7464_then_diarizen-large-v2__diarizen-large-v2__spk_none::outputs__diarizen_uv_48__diarizen-large-v2__default__spk_none_else_current_final` | 120 | 8 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 10 | `if_audio_p90_db_<=_-45.9942_AND_prev_audio_max_p90_db_<=_-40.7464_then_diarizen-large-v2__diarizen-large-v2__spk_none_else_current_final` | 120 | 8 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 11 | `if_audio_p90_db_<=_-46.2244_AND_prev_audio_max_p90_db_<=_-40.7464_then_diarizen-large-v2__diarizen-large-v2__spk_none::outputs__diarizen_uv_48__diarizen-large-v2__default__spk_none_else_current_final` | 120 | 6 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 12 | `if_audio_p90_db_<=_-46.2244_AND_prev_audio_max_p90_db_<=_-40.7464_then_diarizen-large-v2__diarizen-large-v2__spk_none_else_current_final` | 120 | 6 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 13 | `if_audio_p95_db_<=_-44.6773_AND_prev_audio_max_p90_db_<=_-40.7464_then_diarizen-large-v2__diarizen-large-v2__spk_none::outputs__diarizen_uv_48__diarizen-large-v2__default__spk_none_else_current_final` | 120 | 7 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 14 | `if_audio_p95_db_<=_-44.6773_AND_prev_audio_max_p90_db_<=_-40.7464_then_diarizen-large-v2__diarizen-large-v2__spk_none_else_current_final` | 120 | 7 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 15 | `if_fast_audio_speech_ratio_>=_11.9198_AND_prev_audio_max_p90_db_<=_-40.7464_then_diarizen-large-v2__diarizen-large-v2__spk_none::outputs__diarizen_uv_48__diarizen-large-v2__default__spk_none_else_current_final` | 120 | 9 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 16 | `if_fast_audio_speech_ratio_>=_11.9198_AND_prev_audio_max_p90_db_<=_-40.7464_then_diarizen-large-v2__diarizen-large-v2__spk_none_else_current_final` | 120 | 9 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 17 | `if_fast_audio_speech_ratio_>=_19.6909_then_diarizen-large-v2__diarizen-large-v2__spk_none::outputs__diarizen_uv_48__diarizen-large-v2__default__spk_none_else_current_final` | 120 | 5 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 18 | `if_fast_audio_speech_ratio_>=_19.6909_then_diarizen-large-v2__diarizen-large-v2__spk_none_else_current_final` | 120 | 5 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 19 | `if_prev_audio_max_p90_db_<=_-40.7464_AND_slow_audio_speech_ratio_>=_17.3855_then_diarizen-large-v2__diarizen-large-v2__spk_none::outputs__diarizen_uv_48__diarizen-large-v2__default__spk_none_else_current_final` | 120 | 8 | 2/0 | 16.49% | 0.000pp | 6 | 0 |
| 20 | `if_prev_audio_max_p90_db_<=_-40.7464_AND_slow_audio_speech_ratio_>=_17.3855_then_diarizen-large-v2__diarizen-large-v2__spk_none_else_current_final` | 120 | 8 | 2/0 | 16.49% | 0.000pp | 6 | 0 |

## Reading

- This artifact searches new candidate surfaces from existing historical model outputs.
- A deployable policy must improve current DER, improve recording-level positive count, and introduce no negative overlay windows or negative recordings.
- External candidates with partial coverage are analysis surfaces until the candidate source can be reproduced for the full runtime path.
