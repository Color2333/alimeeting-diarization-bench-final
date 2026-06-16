# Selector True-Heldout Split Validation

- Runtime contract: `selector_true_heldout_split_validation_no_metric_claim`
- Status: `blocked_waiting_for_valid_sealed_split`
- Split file: `data/selector_true_heldout_split.csv`
- Minimum true-heldout recordings: `8`
- Split exists: `False`
- Rows: `0`
- True-heldout recordings: `0`
- Overlap with development: `0`
- Missing audio: `0`
- Missing TextGrid: `0`
- Missing required columns: `4`
- No metric claim: `True`
- Blockers: `missing_sealed_split_file, not_enough_true_heldout_recordings`

## Gates

| Gate | Status | Evidence |
|---|---|---|
| `sealed_split_exists` | `blocked` | data/selector_true_heldout_split.csv |
| `required_columns` | `blocked` | recording_id,split,source_manifest,audio_path |
| `true_heldout_count` | `blocked` | 0/8 |
| `no_development_overlap` | `blocked` | split missing |
| `audio_paths_exist` | `blocked` | 0 |
| `textgrid_paths_exist_if_declared` | `blocked` | 0 |
| `no_metric_claim` | `pass` | validation only; no DER/GT/support scoring |

## Reading

- This validator only checks the sealed split contract; it does not compute DER, GT support, or selector metrics.
- A valid true-heldout split must use recordings outside the 120-window development/selector pool.
- `textgrid_path` is optional in the schema, but if declared, every true-heldout row must point to an existing file.
