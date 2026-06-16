# Baseline Headroom Audit

- Runtime contract: `analysis_only_cached_scores_no_runtime_policy_no_live_calls`
- Windows: `120`
- Final DER: `16.49%`
- Best baseline DER: `16.88%` (`slow_base`)
- Beats all baselines: `True`
- Oracle DER: `16.48%`
- Final gap to oracle: `0.01pp`

## Baselines

| Variant | DER | Delta vs Final |
|---|---:|---:|
| `slow_base` | 16.88% | 0.39 pp |
| `rule_recover_policy_sweep_best` | 26.40% | 9.91 pp |
| `rule_recover_matched_label` | 26.43% | 9.94 pp |
| `rule_recover_uncovered_only` | 26.53% | 10.03 pp |
| `fast_base` | 28.56% | 12.07 pp |

## Oracle Variant Counts

| Variant | Windows |
|---|---:|
| `slow_base` | 112 |
| `fast_base` | 5 |
| `rule_recover_matched_label` | 2 |
| `rule_recover_policy_sweep_best` | 1 |

## Top Opportunity Windows

| Window | Final DER | Oracle DER | Gap | Oracle Variant |
|---|---:|---:|---:|---|
| `R8009_M8019:30:11` | 6.59% | 5.40% | 1.19 pp | `fast_base` |
| `R8009_M8018:30:3` | 20.48% | 20.13% | 0.35 pp | `rule_recover_policy_sweep_best` |
| `R8008_M8013:30:2` | 22.65% | 22.64% | 0.01 pp | `slow_base` |
| `R8001_M8004:30:2` | 9.36% | 9.35% | 0.01 pp | `slow_base` |
| `R8008_M8013:30:14` | 9.94% | 9.93% | 0.01 pp | `slow_base` |
| `R8009_M8018:30:4` | 10.05% | 10.04% | 0.01 pp | `slow_base` |
| `R8009_M8018:30:13` | 9.95% | 9.94% | 0.01 pp | `slow_base` |
| `R8009_M8018:30:14` | 7.71% | 7.70% | 0.01 pp | `slow_base` |
| `R8001_M8004:30:4` | 32.45% | 32.44% | 0.01 pp | `slow_base` |
| `R8007_M8010:30:9` | 23.87% | 23.86% | 0.01 pp | `slow_base` |
| `R8007_M8010:30:10` | 27.11% | 27.10% | 0.01 pp | `slow_base` |
| `R8007_M8010:30:11` | 14.69% | 14.68% | 0.01 pp | `slow_base` |
| `R8007_M8011:30:10` | 26.98% | 26.97% | 0.01 pp | `slow_base` |
| `R8009_M8019:30:9` | 9.53% | 9.52% | 0.01 pp | `slow_base` |
| `R8009_M8020:30:13` | 8.12% | 8.11% | 0.01 pp | `slow_base` |
| `R8001_M8004:30:0` | 8.91% | 8.91% | 0.00 pp | `slow_base` |
| `R8001_M8004:30:1` | 25.78% | 25.78% | 0.00 pp | `slow_base` |
| `R8001_M8004:30:3` | 4.17% | 4.17% | 0.00 pp | `slow_base` |
| `R8001_M8004:30:5` | 23.21% | 23.21% | 0.00 pp | `slow_base` |
| `R8001_M8004:30:6` | 31.84% | 31.84% | 0.00 pp | `slow_base` |
