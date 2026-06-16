# Selector True-Heldout Protocol

- Runtime contract: `selector_true_heldout_protocol_no_metric_claim`
- Protocol status: `needs_new_recording_split`
- Fixed policy: `ratio_le_0.65_else_uncovered`
- Split file: `data/selector_true_heldout_split.csv`
- Minimum true-heldout recordings: `8`
- No metric claim: `True`

## Current Development Evidence

- Development recordings: `8`
- Development windows: `120`
- Recording holdout: `8/8` positive
- Weighted DER: `26.51%` vs Fast `28.56%`; delta `2.05%`
- Scope: `dev_only_validation_same_sampled_pool`

## Sealed Split State

- Exists: `False`
- Rows: `0`
- Required columns present: `False`
- True-heldout recordings: `0`
- Overlap with development recordings: `0`
- Missing audio: `0`
- Blockers: `missing_sealed_split_file, not_enough_true_heldout_recordings`

## Candidate Scan

- Scan status: `not_enough_new_local_recordings`
- Local recordings: `8`
- Eligible true-heldout recordings: `0`
- Missing new recordings to minimum: `8`
- Recommendation: Need 8 new recordings outside the current development pool before creating data/selector_true_heldout_split.csv.

## Gates

| Gate | Status | Requirement | Evidence |
|---|---|---|---|
| `sealed_split_exists` | `blocked` | Provide a sealed split CSV before running any metric claim. | data/selector_true_heldout_split.csv |
| `true_heldout_not_in_dev` | `blocked` | No true-heldout recording can appear in the 120-window development/selector pool. | split missing |
| `fixed_policy_before_scoring` | `pass` | Use the frozen selector policy selected before true-heldout scoring. | ratio_le_0.65_else_uncovered |
| `runtime_feature_surface` | `pass` | Selector inputs must not include DER, GT speaker count, oracle labels, or support from held-out scoring. | fast_speech / slow_speech / speaker counts / recover patch deployable features |
| `metric_success_threshold` | `pending` | Weighted DER below Fast, with Miss/FA/Conf and arrival latency reported per recording. | target delta > 0 vs Fast on at least 8 recordings |

## Run Plan

1. Create data/selector_true_heldout_split.csv with new recording ids and audio paths.
2. Run Fast/Slow window extraction on the sealed true-heldout recordings without changing selector thresholds.
3. Apply fixed selector policy ratio_le_0.65_else_uncovered to materialized timeline variants.
4. Report weighted DER/Miss/FA/Conf and rule-writeback arrival latency per recording.
5. Promote selector claim only if weighted DER beats Fast and leakage checks pass.

## Development Recordings Already Used

`R8001_M8004`, `R8003_M8001`, `R8007_M8010`, `R8007_M8011`, `R8008_M8013`, `R8009_M8018`, `R8009_M8019`, `R8009_M8020`
