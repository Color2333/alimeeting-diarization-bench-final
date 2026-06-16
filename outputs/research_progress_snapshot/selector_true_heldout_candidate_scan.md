# Selector True-Heldout Candidate Scan

- Runtime contract: `selector_true_heldout_candidate_scan_no_metric_claim`
- Status: `not_enough_new_local_recordings`
- Local recordings scanned: `8`
- Development recordings: `8`
- Eligible true-heldout recordings: `0`
- Missing new recordings to minimum: `8`
- No metric claim: `True`
- Sealed split written: `False`
- Recommendation: Need 8 new recordings outside the current development pool before creating data/selector_true_heldout_split.csv.

## Recording Scan

| Recording | Eligible | Blockers | Far audio | Far TextGrid | Near channels |
|---|---|---|---|---|---:|
| `R8001_M8004` | `False` | already_in_120_window_development_pool | `True` | `True` | 4 |
| `R8003_M8001` | `False` | already_in_120_window_development_pool | `True` | `True` | 4 |
| `R8007_M8010` | `False` | already_in_120_window_development_pool | `True` | `True` | 4 |
| `R8007_M8011` | `False` | already_in_120_window_development_pool | `True` | `True` | 4 |
| `R8008_M8013` | `False` | already_in_120_window_development_pool | `True` | `True` | 3 |
| `R8009_M8018` | `False` | already_in_120_window_development_pool | `True` | `True` | 2 |
| `R8009_M8019` | `False` | already_in_120_window_development_pool | `True` | `True` | 2 |
| `R8009_M8020` | `False` | already_in_120_window_development_pool | `True` | `True` | 2 |

## Reading

- This scan only inspects local recording availability; it does not create the sealed split used for scoring.
- Near-channel files for the same meeting are not counted as new true-heldout recordings.
- Every local Eval_Ali meeting currently overlaps the 120-window development/selector pool, so true-heldout scoring remains blocked.
