| Category | Patches | Windows | GT overlap sec | True support rate | Patch types |
|---|---:|---:|---:|---:|---|
| guard_or_quarantine | 39 | 2 | 61.128 | 61.5% | align_slow_segment 10 / boundary_fix_or_relabel 27 / recover_slow_segment 2 |
| llm_defer_review | 88 | 46 | 81.560 | 90.9% | recover_slow_segment 74 / suppress_fast_candidate 14 |
| non_accept_review | 2 | 2 | 0.287 | 0.0% | recover_slow_segment 2 |
| rule_accept_needs_review | 761 | 95 | 2995.340 | 98.6% | boundary_fix_or_relabel 605 / keep_fast_supported 152 / suppress_fast_candidate 4 |
| rule_auto_writeback | 418 | 54 | 1367.230 | 99.8% | boundary_fix_or_relabel 273 / keep_fast_supported 145 |
| rule_label_only_writeback | 86 | 38 | 40.450 | 96.5% | boundary_fix_or_relabel 86 |
| rule_recover_writeback | 95 | 47 | 739.957 | 100.0% | recover_slow_segment 95 |
| rule_reference_only | 1175 | 118 | 5168.888 | 99.4% | align_slow_segment 1175 |

| Summary | Value |
|---|---:|
| Rule writeback patches | 599 |
| Rule writeback GT overlap sec | 2147.637 |
| Recover writeback GT overlap sec | 739.957 |
| Recover unique Fast-miss sec | 197.360 |
| Recover / Fast miss sec | 60.2% |
| Avg Slow correction latency | 24.65s |
