# True-Heldout Readiness

- Status: `blocked_missing_sealed_split_and_new_recordings`
- Split file: `data/selector_true_heldout_split.csv`
- True-heldout recordings: `0/8`
- Eligible local candidates: `0`
- Missing new recordings: `8`
- Promotion gate: `dev_metric_pass_promotion_blocked` (`blocked`)
- No metric claim: `True`

## Gates

| Status | Gate | Evidence |
|---|---|---|
| `blocked` | `sealed_split_exists` | `"data/selector_true_heldout_split.csv"` |
| `blocked` | `required_columns_present` | `{"missing_required_columns": 4, "required_columns": ["recording_id", "split", "source_manifest", "audio_path"]}` |
| `blocked` | `true_heldout_count` | `"0/8"` |
| `blocked` | `no_development_overlap` | `{"overlap_recordings": [], "overlap_with_development": 0}` |
| `blocked` | `local_candidate_pool_available` | `{"eligible_local_candidates": 0, "minimum_true_heldout_recordings": 8}` |
| `pass` | `no_metric_claim` | `"readiness-only; no DER or support scoring"` |

## Next Actions

- `add_8_new_recordings_outside_development_pool`
- `create_data_selector_true_heldout_split_csv`
- `run_fast_slow_extraction_without_changing_selector_thresholds`
- `score_frozen_selector_on_true_heldout`

## Reading

- This report is readiness-only: it does not run DER scoring or support a generalized metric claim.
- Development-pool baseline wins remain useful, but promotion needs a sealed true-heldout split with new recordings.
