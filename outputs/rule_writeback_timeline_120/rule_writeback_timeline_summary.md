# Rule Writeback Timeline Evaluation

| Variant | Windows | DER | Median DER | Miss | FA | Conf | Spk match | Boundary replaced | Recover added | Interpretation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| fast_base | 120 | 28.56% | 21.29% | 19.96% | 5.41% | 3.20% | 54.2% | 0 | 0 | Original realtime first-pass baseline. |
| fast_base_speaker_union | 120 | 28.56% | 21.29% | 19.96% | 5.41% | 3.20% | 54.2% | 0 | 0 | Fast baseline after merging overlapping same-speaker fragments. |
| rule_boundary_recover | 120 | 32.54% | 27.60% | 12.86% | 14.84% | 4.83% | 54.2% | 359 | 95 | Also applies accepted boundary replacements; closest current conservative merged timeline. |
| rule_boundary_recover_no_same_overlap | 120 | 32.54% | 27.60% | 12.86% | 14.84% | 4.83% | 54.2% | 359 | 77 | Boundary+recover with same-speaker overlap subtraction. |
| rule_boundary_recover_speaker_union | 120 | 32.54% | 27.61% | 12.86% | 14.84% | 4.83% | 54.2% | 359 | 95 | Boundary+recover plus same-speaker union sanitizer. |
| rule_recover_identity_selector | 120 | 26.40% | 20.16% | 15.57% | 5.77% | 5.05% | 54.2% | 0 | 93 | Matched-label recover; allow overlap only when Slow predicts more speakers than Fast. |
| rule_recover_matched_label | 120 | 26.43% | 20.16% | 15.39% | 6.02% | 5.02% | 54.2% | 0 | 95 | Adds accepted recover segments with matched Fast labels when available. |
| rule_recover_matched_label_speaker_union | 120 | 26.43% | 20.16% | 15.39% | 6.02% | 5.02% | 54.2% | 0 | 95 | Matched-label recover plus same-speaker union sanitizer. |
| rule_recover_matched_no_same_overlap | 120 | 26.43% | 20.16% | 15.39% | 6.01% | 5.02% | 54.2% | 0 | 93 | Matched-label recover, subtracting same-speaker overlap before insertion. |
| rule_recover_new_label | 120 | 30.07% | 25.92% | 14.17% | 11.53% | 4.37% | 52.5% | 0 | 95 | Adds accepted recover segments with new slow labels; tests speech recovery without identity linking. |
| rule_recover_policy_sweep_best | 120 | 26.40% | 20.16% | 15.57% | 5.77% | 5.05% | 54.2% | 0 | 93 | Policy-search best: matched recover if slow_spk > fast_spk or fast/slow speech ratio <= 0.60. |
| rule_recover_uncovered_only | 120 | 26.53% | 20.16% | 15.95% | 5.54% | 5.03% | 54.2% | 0 | 83 | Matched-label recover only where Fast has no predicted speech; lowest-risk miss patch. |
| rule_recover_uncovered_only_speaker_union | 120 | 26.53% | 20.16% | 15.95% | 5.54% | 5.03% | 54.2% | 0 | 83 | Uncovered-only recover plus same-speaker union sanitizer. |
| slow_base | 120 | 16.88% | 10.92% | 4.99% | 6.92% | 4.98% | 67.5% | 0 | 0 | Full DiariZen mature-window replacement baseline. |

## Reading

- This is a timeline-level score, not just patch coverage.
- Ground truth is used only after materializing predictions for DER scoring.
- If recover variants lower Miss but raise Conf/FA, the next bottleneck is identity assignment and overlap-aware insertion, not acoustic detection.
