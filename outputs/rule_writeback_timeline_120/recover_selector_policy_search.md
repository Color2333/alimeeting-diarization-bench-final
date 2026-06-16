# Recover Selector Policy Search

| Rank | Policy | DER | Miss | FA | Conf | Matched | Uncovered | Fast |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | ratio_le_0.65_else_uncovered | 26.30% | 15.58% | 5.64% | 5.08% | 13 | 34 | 73 |
| 2 | ratio_le_0.70_else_uncovered | 26.30% | 15.58% | 5.64% | 5.08% | 15 | 32 | 73 |
| 3 | ratio_le_0.25_else_uncovered | 26.33% | 15.68% | 5.58% | 5.07% | 5 | 42 | 73 |
| 4 | spk_gt_and_ratio_le_0.25 | 26.33% | 15.68% | 5.58% | 5.07% | 5 | 42 | 73 |
| 5 | ratio_le_0.30_else_uncovered | 26.33% | 15.68% | 5.58% | 5.07% | 5 | 42 | 73 |
| 6 | spk_gt_and_ratio_le_0.30 | 26.33% | 15.68% | 5.58% | 5.07% | 5 | 42 | 73 |
| 7 | ratio_le_0.35_else_uncovered | 26.33% | 15.68% | 5.58% | 5.07% | 5 | 42 | 73 |
| 8 | spk_gt_and_ratio_le_0.35 | 26.33% | 15.68% | 5.58% | 5.07% | 5 | 42 | 73 |
| 9 | ratio_le_0.40_else_uncovered | 26.33% | 15.68% | 5.58% | 5.07% | 5 | 42 | 73 |
| 10 | spk_gt_and_ratio_le_0.40 | 26.33% | 15.68% | 5.58% | 5.07% | 5 | 42 | 73 |
| 11 | ratio_le_0.45_else_uncovered | 26.33% | 15.68% | 5.58% | 5.07% | 5 | 42 | 73 |
| 12 | spk_gt_and_ratio_le_0.45 | 26.33% | 15.68% | 5.58% | 5.07% | 5 | 42 | 73 |
| 13 | spk_gt_or_ratio_le_0.65 | 26.34% | 15.50% | 5.78% | 5.06% | 24 | 23 | 73 |
| 14 | spk_gt_or_ratio_le_0.70 | 26.34% | 15.50% | 5.78% | 5.06% | 24 | 23 | 73 |
| 15 | ratio_le_0.75_else_uncovered | 26.35% | 15.53% | 5.73% | 5.09% | 21 | 26 | 73 |

## Reading

- Policies use only deployable Fast/Slow prediction features.
- Ground truth is used only to rank policies after materialized timeline scoring.
- The selected policy should be validated on a larger held-out sample before being treated as final.
