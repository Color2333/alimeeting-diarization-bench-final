# Post-Live Time Metric Extractor

- Runtime contract: `post_live_time_metric_extractor_no_live_calls`
- Status: `blocked_waiting_live_outputs`
- Extractor rows: `3`
- P0 / P1 rows: `1` / `2`
- Missing output rows: `3`
- Blocked extractor rows: `3`
- Ready time metric rows: `0`
- Computed time metric rows: `0`
- Expected rows total: `382`
- Observed rows total: `0`
- Successful rows total: `0`
- Parse error rows: `0`
- Retry rows total: `0`
- Expected live calls: `382`
- Missing output surfaces: `3`
- Time statistic rows: `9`
- Planned live calls: `382`
- P0 planned live calls: `139`
- Ready to promote: `0`
- Traceability rows: `54`
- Live calls performed by builder: `0`
- No scoring commands executed: `True`
- No new metric claim: `True`

| Metric | Priority | Surface | Status | Expected | Observed | Avg | P50 | P95 | Max | Boundary |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| `deepseek_resume_time_metric_extract` | `P0` | `deepseek_resume_after_top3` | `blocked_missing_output` | 139 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | `not_claimable_until_resume_output_audit_scoring_and_traceability` |
| `qwen_backup_time_metric_extract` | `P1` | `qwen_full_backup` | `blocked_missing_output` | 147 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | `fallback_only_not_primary_latency_claim` |
| `omni48_label_time_metric_extract` | `P1` | `omni48_label_only` | `blocked_missing_output` | 96 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | `label_only_latency_not_guard_or_timeline_claim` |

## Reading

- This extractor reads pending live output JSONL files only; it performs no live/API/model/scoring calls.
- It computes time metrics only when the expected live rows exist and parse cleanly.
- DeepSeek remains unclaimable until output audit, safety scoring, comparison, promotion, and traceability pass.
- Qwen remains fallback-only and Omni48 remains label-only, so this extractor does not create a primary timeline latency claim.
