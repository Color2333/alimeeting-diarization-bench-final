# Slow Sanitization Policy Search

- Runtime contract: `slow_sanitization_policy_search_no_live_calls_predicted_timeline_features_only`
- Status: `no_robust_sanitizer_found`
- Best policy: `slow`
- Best DER: `16.88%`
- Slow baseline DER: `16.88%`
- Delta vs Slow: `0.00pp`
- Bootstrap P(beats Slow): `0.0%`
- Holdout positive splits: `0/8`

## Top Policies

| Rank | Policy | DER | Miss | FA | Conf | Counters |
|---:|---|---:|---:|---:|---:|---|
| 1 | `slow` | 16.88% | 4.99% | 6.92% | 4.98% | `{}` |
| 2 | `slow__min_duration0p2` | 16.88% | 5.13% | 6.84% | 4.91% | `{"drop_short": 96}` |
| 3 | `slow__merge_gap0p1` | 16.89% | 4.97% | 6.95% | 4.96% | `{"merge_removed": 44}` |
| 4 | `slow__merge_gap0p2` | 16.94% | 4.92% | 7.05% | 4.97% | `{"merge_removed": 85}` |
| 5 | `slow__min_duration0p4` | 17.19% | 5.95% | 6.50% | 4.74% | `{"drop_short": 265}` |
| 6 | `slow__min_fast_overlap_sec0p05` | 17.75% | 6.32% | 6.71% | 4.72% | `{"drop_low_fast_overlap_sec": 124}` |
| 7 | `slow__min_fast_overlap_ratio0p05` | 17.75% | 6.30% | 6.72% | 4.73% | `{"drop_low_fast_overlap_ratio": 86}` |
| 8 | `slow__min_fast_overlap_sec0p1` | 17.75% | 6.40% | 6.68% | 4.67% | `{"drop_low_fast_overlap_sec": 145}` |
| 9 | `slow__min_fast_overlap_ratio0p1` | 18.65% | 7.25% | 6.71% | 4.69% | `{"drop_low_fast_overlap_ratio": 96}` |
| 10 | `slow__max_speech_ratio1p4__cap_actiondrop_unsupported` | 19.47% | 8.13% | 6.66% | 4.68% | `{"cap_drop": 71}` |
| 11 | `slow__max_speech_ratio1p4__cap_actionfast` | 20.93% | 10.44% | 6.56% | 3.93% | `{"cap_fast_fallback": 21}` |
| 12 | `slow__max_speech_ratio1p2__cap_actiondrop_unsupported` | 24.01% | 13.29% | 6.31% | 4.41% | `{"cap_drop": 139}` |
| 13 | `slow__max_speech_ratio1p2__cap_actionfast` | 24.06% | 14.35% | 6.19% | 3.51% | `{"cap_fast_fallback": 43}` |
| 14 | `fast` | 28.56% | 19.96% | 5.41% | 3.20% | `{"fast_fallback": 120}` |

## Reading

- Sanitizers use only predicted Fast/Slow timelines.
- DER/GT is used only after materialization for scoring.
- If the best policy is not robust on bootstrap/holdout, it should not replace the default system path.
