# Baseline Leaderboard Audit

- Status: `pass`
- Final DER: `16.4923%`
- Full-coverage baselines: `8`
- Beats all full-coverage baselines: `True`
- Best full baseline: `runtime_same_window/slow_base` / `16.8809%`
- Partial/non-comparable candidates: `0`

## Full Current-Window Pool

| Rank | Candidate | DER | Delta vs Final | Source |
|---:|---|---:|---:|---|
| 1 | `runtime_same_window/slow_base` | 16.8809% | 0.3886pp | `runtime_baseline_comparison` |
| 2 | `diarizen-large-v2/diarizen-large-v2/spk_none` | 16.8809% | 0.3886pp | `historical_summary_results` |
| 3 | `diarizen-large-v2/diarizen-large-v2/spk_none` | 16.8809% | 0.3886pp | `historical_summary_results` |
| 4 | `runtime_same_window/rule_recover_policy_sweep_best` | 26.3975% | 9.9052pp | `runtime_baseline_comparison` |
| 5 | `runtime_same_window/rule_recover_matched_label` | 26.4315% | 9.9392pp | `runtime_baseline_comparison` |
| 6 | `runtime_same_window/rule_recover_uncovered_only` | 26.5261% | 10.0337pp | `runtime_baseline_comparison` |
| 7 | `runtime_same_window/fast_base` | 28.5637% | 12.0714pp | `runtime_baseline_comparison` |
| 8 | `nemo-sortformer-4spk-v1/nemo-sortformer-4spk-v1/spk_none` | 28.5637% | 12.0714pp | `historical_summary_results` |

## Partial / Not Final-Comparable

| Candidate | Coverage | DER on overlap | Note |
|---|---:|---:|---|

## Reading

- Only `full_current_window_pool` rows can support the current all-cached metric claim.
- Partial runs are useful signals, but they cannot prove the final system beats all baselines over the full 120-window development pool.
- This audit uses existing artifacts only and performs no model inference or live API calls.
