# Clipped Baseline Audit

- Runtime contract: `clipped_baseline_fairness_audit_no_live_calls`
- Status: `pass`
- Windows: `120`
- Final DER: `16.49%`
- Best clipped baseline: `slow_base` / `16.88%`
- Delta vs best clipped baseline: `0.387pp`
- Beats all clipped baselines: `True`

## Baselines

| Baseline | DER | Delta vs Final | Adjusted | Dropped | Trimmed ms |
|---|---:|---:|---:|---:|---:|
| `slow_base` | 16.88% | 0.387pp | 103 | 4 | 22664 |
| `rule_recover_policy_sweep_best` | 26.40% | 9.905pp | 11 | 0 | 2514 |
| `rule_recover_matched_label` | 26.43% | 9.939pp | 11 | 0 | 2514 |
| `rule_recover_uncovered_only` | 26.53% | 10.034pp | 9 | 1 | 2090 |
| `fast_base` | 28.56% | 12.071pp | 0 | 0 | 0 |

## Reading

- Baselines are scored after the same local `[0, window_size]` clipping used for final runtime output.
- This is a fairness audit for metric claims; it does not change the baseline source artifacts.
