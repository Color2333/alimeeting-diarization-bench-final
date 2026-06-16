# Post-Live Time Metric Statistics Plan

- Runtime contract: `post_live_time_metric_statistics_plan_no_live_calls`
- Status: `blocked_waiting_live_outputs`
- Time statistic rows: `9`
- P0 / P1 rows: `7` / `2`
- Claim-now preserve rows: `4`
- Blocked/waiting rows: `5`
- Fallback-only rows: `1`
- Label-only rows: `1`
- Stage-arrival rows: `4`
- Post-live statistic rows: `4`
- Formula count: `9`
- Claim-now SLO pass: `4/4`
- Guard P95 margin seconds: `1.151`
- Metric contracts: `8`
- Schema contracts: `8`
- Latency claim rows: `8`
- Planned live calls: `382`
- P0 planned live calls: `139`
- Expected live calls: `382`
- Missing output surfaces: `3`
- Ready to promote: `0`
- Traceability rows: `54`
- Live calls performed by builder: `0`
- No scoring commands executed: `True`
- No new metric claim: `True`

| Metric | Priority | Surface | State | Family | Expected rows | Boundary |
|---|---|---|---|---|---:|---|
| `fast_first_output_latency_current` | `P0` | `runtime_120_windows` | `claim_now_preserve` | `stage_arrival_latency` | 0 | `claim_now_latency_preserve` |
| `rule_writeback_latency_current` | `P0` | `runtime_120_windows` | `claim_now_preserve` | `stage_arrival_latency` | 0 | `claim_now_latency_preserve` |
| `runtime_safe_guard_latency_current` | `P0` | `104_proxy_flagged_windows` | `claim_now_preserve_with_tight_margin_watch` | `stage_arrival_latency` | 0 | `claim_now_latency_preserve_no_broader_claim` |
| `llm_review_signal_latency_current` | `P0` | `4_review_cases` | `claim_now_memory_protection_preserve` | `stage_arrival_latency` | 0 | `review_only_no_timeline_override` |
| `deepseek_resume_call_latency_stats` | `P0` | `deepseek_resume_after_top3` | `blocked_waiting_live_outputs` | `llm_call_latency` | 139 | `not_claimable_until_resume_output_audit_scoring_and_traceability` |
| `deepseek_parent_completion_latency_stats` | `P0` | `deepseek_resume_after_top3` | `blocked_waiting_comparison_summary` | `parent_window_completion_latency` | 147 | `required_before_full_surface_latency_claim` |
| `qwen_backup_latency_stats` | `P1` | `qwen_full_backup` | `fallback_only_waiting_credentials` | `fallback_llm_call_latency` | 147 | `fallback_only_not_primary_latency_claim` |
| `omni48_label_latency_stats` | `P1` | `omni48_label_only` | `blocked_waiting_live_outputs` | `omni_label_call_latency` | 96 | `label_only_latency_not_guard_or_timeline_claim` |
| `report_ppt_time_claim_refresh` | `P0` | `report_ppt` | `waiting_post_live_promotion` | `time_claim_traceability` | 0 | `report_ppt_sync_required_before_time_metric_claim_promotion` |

## Formulas

### fast_first_output_latency_current

- Source artifacts: `outputs/research_progress_snapshot/runtime_latency_budget_ledger.md`
- Formula: `avg_seconds=0.383; p95_seconds=0.445; SLO avg<=1s and p95<=1s`
- Promotion gate: `current_claim_now_slo`
- Report/PPT effect: `keep current first visible update timing claim`

### rule_writeback_latency_current

- Source artifacts: `outputs/research_progress_snapshot/runtime_latency_budget_ledger.md`
- Formula: `avg_seconds=24.647; p95_seconds=28.334; SLO avg<=30s and p95<=35s`
- Promotion gate: `current_claim_now_slo`
- Report/PPT effect: `keep bounded rule-writeback timing claim`

### runtime_safe_guard_latency_current

- Source artifacts: `outputs/research_progress_snapshot/runtime_latency_budget_ledger.md; outputs/research_progress_snapshot/latency_risk_margin_audit.md`
- Formula: `avg_seconds=44.918; p95_seconds=63.849; margin_seconds=1.151`
- Promotion gate: `current_claim_now_slo_and_risk_watch`
- Report/PPT effect: `keep current guard timing claim but retain tight-margin warning`

### llm_review_signal_latency_current

- Source artifacts: `outputs/research_progress_snapshot/runtime_latency_budget_ledger.md`
- Formula: `avg_seconds=46.097; p95_seconds=55.8; memory-protection only`
- Promotion gate: `current_claim_now_review_only`
- Report/PPT effect: `keep review timing as memory-protection evidence only`

### deepseek_resume_call_latency_stats

- Source artifacts: `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl; outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_summary.json`
- Formula: `from successful JSONL rows: count, avg(call_seconds), p50, p95, max, wall_seconds, retry_count`
- Promotion gate: `deepseek_split20_resume_latency`
- Report/PPT effect: `feed full-surface split20 latency only after safety and comparison summaries pass`

### deepseek_parent_completion_latency_stats

- Source artifacts: `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.json`
- Formula: `from split comparison: original_max_call_seconds vs split_max_call_seconds; parent avg/max; token_multiplier`
- Promotion gate: `deepseek_split20_resume_latency`
- Report/PPT effect: `promote split20 latency only if 104 parents / 147 calls are covered and harmful_accepts == 0`

### qwen_backup_latency_stats

- Source artifacts: `outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl`
- Formula: `fallback-only: count, avg(call_seconds), p95, max, wall_seconds, token_multiplier`
- Promotion gate: `qwen_full_backup_claim`
- Report/PPT effect: `keep as fallback timing context, not primary latency claim`

### omni48_label_latency_stats

- Source artifacts: `outputs/omni_guard/omni_expansion_48_live.jsonl`
- Formula: `label-only: avg(first_text_seconds if present), avg/p95/max(call_seconds), per-model split`
- Promotion gate: `omni48_label_metrics`
- Report/PPT effect: `report only as label latency and quality; never timeline writeback`

### report_ppt_time_claim_refresh

- Source artifacts: `outputs/research_progress_snapshot/post_live_latency_claim_matrix.md; outputs/research_progress_snapshot/report_ppt_traceability.md`
- Formula: `after refresh: latest_artifact_validation pass; traceability fully covered; no missing source rows`
- Promotion gate: `report_ppt_traceability_after_promotion`
- Report/PPT effect: `force report/PPT wording to match claim-now, promoted, fallback-only, and blocked time surfaces`

## Reading

- This plan fixes the statistics formulas for current and post-live timing metrics.
- Claim-now rows preserve existing stage-arrival timing; post-live rows stay blocked until live outputs, scoring, promotion, and traceability pass.
- Qwen remains fallback-only and Omni48 remains label-only, so neither can promote a primary timeline latency claim from this plan.
- The builder performs no live/API/model/scoring calls, writes no secret values, and makes no new metric claim.
