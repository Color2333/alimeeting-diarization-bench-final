# Audio Boundary Adjustment Search

- Runtime contract: `audio_boundary_adjustment_no_live_calls_audio_features_only`
- Status: `no_robust_audio_boundary_policy_found`
- Windows: `120`
- Candidate policies: `91`
- Best policy: `boundary_expand__modemean__pad0p1__search_pad0p25__max_total_expand_sec0p1__min_active_sec0p05__prevent_same_speaker_overlapTrue`
- Best DER: `16.88%`
- Slow baseline DER: `16.88%`
- Delta vs Slow: `0.00pp`
- Bootstrap P(beats Slow): `56.2%`
- Holdout positive splits: `1/8`
- Holdout weighted delta vs Slow: `-0.02pp`

## Top Policies

| Rank | Policy | DER | Miss | FA | Conf | Pred speech | Counters |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | `boundary_expand__modemean__pad0p1__search_pad0p25__max_total_expand_sec0p1__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.88% | 4.91% | 6.98% | 4.98% | 34.88s | `{"expand_blocked": 778, "expanded": 183, "overlap_reverted_windows": 3, "same_speaker_overlap_capped": 111, "same_speaker_overlap_pairs": 3, "unchanged_no_activity": 154}` |
| 2 | `boundary_expand__modemean__pad0p1__search_pad0p5__max_total_expand_sec0p1__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.88% | 4.93% | 6.97% | 4.98% | 34.88s | `{"expand_blocked": 945, "expanded": 123, "overlap_reverted_windows": 2, "same_speaker_overlap_capped": 250, "same_speaker_overlap_pairs": 2, "unchanged_no_activity": 109}` |
| 3 | `slow` | 16.88% | 4.99% | 6.92% | 4.98% | 34.95s | `{"slow_base": 120}` |
| 4 | `boundary_expand__modemean__search_pad0p5__max_total_expand_sec0p1__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.89% | 4.96% | 6.96% | 4.97% | 34.86s | `{"expand_blocked": 906, "expanded": 77, "overlap_reverted_windows": 2, "same_speaker_overlap_capped": 218, "same_speaker_overlap_pairs": 3, "unchanged_no_activity": 109}` |
| 5 | `boundary_expand__modemax__search_pad0p5__max_total_expand_sec0p1__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.89% | 4.96% | 6.95% | 4.97% | 34.87s | `{"expand_blocked": 1027, "expanded": 68, "overlap_reverted_windows": 1, "same_speaker_overlap_capped": 263, "same_speaker_overlap_pairs": 2, "unchanged_no_activity": 43}` |
| 6 | `boundary_expand__modemax__pad0p1__search_pad0p5__max_total_expand_sec0p1__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.89% | 4.93% | 6.98% | 4.98% | 34.90s | `{"expand_blocked": 1059, "expanded": 126, "overlap_reverted_windows": 3, "same_speaker_overlap_capped": 297, "same_speaker_overlap_pairs": 3, "unchanged_no_activity": 43}` |
| 7 | `boundary_expand__modemean__pad0p1__search_pad0p1__max_total_expand_sec0p1__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.89% | 4.89% | 7.02% | 4.99% | 34.89s | `{"expand_blocked": 643, "expanded": 234, "overlap_reverted_windows": 3, "same_speaker_overlap_capped": 71, "same_speaker_overlap_pairs": 3, "unchanged_no_activity": 183}` |
| 8 | `boundary_expand__modemax__search_pad0p25__max_total_expand_sec0p1__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.89% | 4.94% | 6.98% | 4.97% | 34.88s | `{"expand_blocked": 816, "expanded": 130, "overlap_reverted_windows": 1, "same_speaker_overlap_capped": 106, "same_speaker_overlap_pairs": 1, "unchanged_no_activity": 76}` |
| 9 | `boundary_expand__modemax__pad0p1__search_pad0p25__max_total_expand_sec0p1__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.90% | 4.91% | 7.01% | 4.98% | 34.91s | `{"expand_blocked": 900, "expanded": 193, "overlap_reverted_windows": 2, "same_speaker_overlap_capped": 134, "same_speaker_overlap_pairs": 2, "unchanged_no_activity": 76}` |
| 10 | `boundary_expand__modemean__search_pad0p25__max_total_expand_sec0p1__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.91% | 4.94% | 6.99% | 4.98% | 34.87s | `{"expand_blocked": 693, "expanded": 131, "overlap_reverted_windows": 5, "same_speaker_overlap_capped": 86, "same_speaker_overlap_pairs": 5, "unchanged_no_activity": 154}` |
| 11 | `boundary_expand__modemax__pad0p1__search_pad0p1__max_total_expand_sec0p1__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.91% | 4.88% | 7.04% | 4.98% | 34.91s | `{"expand_blocked": 758, "expanded": 255, "overlap_reverted_windows": 3, "same_speaker_overlap_capped": 82, "same_speaker_overlap_pairs": 3, "unchanged_no_activity": 104}` |
| 12 | `boundary_expand__modemax__search_pad0p5__max_total_expand_sec0p25__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.93% | 4.87% | 7.10% | 4.95% | 34.95s | `{"expand_blocked": 938, "expanded": 157, "overlap_reverted_windows": 13, "same_speaker_overlap_capped": 263, "same_speaker_overlap_pairs": 16, "unchanged_no_activity": 43}` |
| 13 | `boundary_expand__modemean__pad0p1__search_pad0p5__max_total_expand_sec0p25__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.94% | 4.84% | 7.15% | 4.96% | 34.97s | `{"expand_blocked": 862, "expanded": 206, "overlap_reverted_windows": 9, "same_speaker_overlap_capped": 250, "same_speaker_overlap_pairs": 11, "unchanged_no_activity": 109}` |
| 14 | `boundary_expand__modemax__pad0p1__search_pad0p5__max_total_expand_sec0p25__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.94% | 4.82% | 7.14% | 4.98% | 34.98s | `{"expand_blocked": 974, "expanded": 211, "overlap_reverted_windows": 12, "same_speaker_overlap_capped": 297, "same_speaker_overlap_pairs": 14, "unchanged_no_activity": 43}` |
| 15 | `boundary_expand__modemax__search_pad0p1__max_total_expand_sec0p1__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.95% | 4.90% | 7.08% | 4.96% | 34.90s | `{"expand_blocked": 558, "expanded": 245, "overlap_reverted_windows": 4, "same_speaker_overlap_capped": 42, "same_speaker_overlap_pairs": 4, "unchanged_no_activity": 104}` |
| 16 | `boundary_expand__modemean__search_pad0p1__max_total_expand_sec0p1__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.95% | 4.92% | 7.06% | 4.98% | 34.89s | `{"expand_blocked": 457, "expanded": 226, "overlap_reverted_windows": 6, "same_speaker_overlap_capped": 38, "same_speaker_overlap_pairs": 6, "unchanged_no_activity": 183}` |
| 17 | `boundary_expand__modemean__search_pad0p5__max_total_expand_sec0p25__min_active_sec0p05__prevent_same_speaker_overlapTrue` | 16.96% | 4.87% | 7.11% | 4.98% | 34.95s | `{"expand_blocked": 820, "expanded": 163, "overlap_reverted_windows": 11, "same_speaker_overlap_capped": 218, "same_speaker_overlap_pairs": 14, "unchanged_no_activity": 109}` |
| 18 | `boundary_trim__modemax__pad0p2__max_total_trim_sec0p25__min_active_sec0p1` | 16.96% | 5.35% | 6.69% | 4.93% | 34.72s | `{"same_speaker_overlap_pairs": 0, "trim_blocked": 176, "trimmed": 297, "unchanged_no_activity": 203}` |
| 19 | `boundary_trim__modemax__pad0p2__max_total_trim_sec0p25__min_active_sec0p05` | 16.97% | 5.38% | 6.67% | 4.92% | 34.71s | `{"same_speaker_overlap_pairs": 0, "trim_blocked": 187, "trimmed": 318, "unchanged_no_activity": 148}` |
| 20 | `boundary_trim__modemax__pad0p2__max_total_trim_sec0p25__min_active_sec0p03` | 16.98% | 5.40% | 6.66% | 4.92% | 34.70s | `{"same_speaker_overlap_pairs": 0, "trim_blocked": 197, "trimmed": 327, "unchanged_no_activity": 124}` |

## Reading

- Policies use only audio activity masks and Slow predicted timelines at runtime.
- They adjust boundaries only; they do not delete complete Slow segments.
- DER/GT is used only after materialization for scoring and validation.
