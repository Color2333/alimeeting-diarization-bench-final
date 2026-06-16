# Live Metric Extraction Contract

- Runtime contract: `live_metric_extraction_contract_no_live_calls`
- Status: `blocked_waiting_live_outputs`
- Metric contracts: `8`
- P0 metric contracts: `4`
- Time metric contracts: `3`
- Safety metric contracts: `2`
- Omni metric contracts: `2`
- Ready to score: `0`
- Expected live calls: `382`
- Expected input calls: `676`
- Missing output surfaces: `3`
- Ready to promote: `0`
- Live calls performed by builder: `0`
- No scoring commands executed: `True`
- No new metric claim: `True`

| Metric | Surface | Priority | Family | Dependency | Fields | Promotion gate | Claim status |
|---|---|---|---|---|---|---|---|
| `deepseek_resume_safety_zero_harm` | `deepseek_resume_after_top3` | `P0` | `llm_safety` | `deepseek_resume_safety` | harmful_accepts; conservative_blocks; missing_patch_eval; parent_window_decision_override | `deepseek_split20_resume_safety` | `not_claimable_until_resume_safety_summary_exists` |
| `deepseek_resume_call_latency` | `deepseek_resume_after_top3` | `P0` | `llm_latency` | `deepseek_full_split20_comparison` | parent_windows; split_calls; original_max_call_seconds; split_max_call_seconds; split_parent_avg_max_call_seconds; wall_seconds | `deepseek_split20_resume_latency` | `not_claimable_until_full_split20_comparison_exists` |
| `deepseek_resume_token_multiplier` | `deepseek_resume_after_top3` | `P0` | `llm_quota_efficiency` | `deepseek_full_split20_comparison` | split_total_tokens; original_total_tokens; token_multiplier | `deepseek_split20_resume_latency` | `planning_support_until_full_split20_comparison_exists` |
| `qwen_backup_safety_zero_harm` | `qwen_full_backup` | `P1` | `llm_backup_safety` | `qwen_full_backup_safety` | harmful_accepts; conservative_blocks; missing_patch_eval; parent_window_decision_override | `qwen_full_backup_claim` | `fallback_only_not_primary_claim` |
| `qwen_backup_call_latency` | `qwen_full_backup` | `P1` | `llm_backup_latency` | `qwen_full_backup_comparison` | parent_windows; split_calls; split_max_call_seconds; wall_seconds; token_multiplier | `qwen_full_backup_claim` | `fallback_only_not_primary_latency_claim` |
| `omni48_label_quality` | `omni48_label_only` | `P1` | `omni_label_quality` | `omni48_label_summary` | high_positive_rate; clean_false_positive_rate; quarantines; defers; risk_counts | `omni48_label_metrics` | `label_only_no_timeline_writeback` |
| `omni48_call_latency` | `omni48_label_only` | `P1` | `omni_call_latency` | `omni48_label_summary` | avg_call_seconds; p95_call_seconds; max_call_seconds | `omni48_label_metrics` | `pending_96_call_live_latency` |
| `post_live_promotion_sync` | `all_live_surfaces` | `P0` | `promotion_traceability` | `post_live_claim_promotion_gate` | ready_to_promote_count; traceability_rows; fully_covered_rows; missing_source_rows | `report_ppt_sync_after_promotion` | `promote_only_after_output_audit_scoring_slo_and_traceability_pass` |

## Reading

- This contract defines which post-live metrics may be extracted after output audit and scoring readiness unblock.
- DeepSeek P0 metrics require both resume safety and full split20 comparison outputs before promotion.
- Qwen remains fallback-only unless a later promotion gate explicitly changes that boundary.
- Omni48 metrics are label-only and cannot write timeline changes back.
- The builder only reads local artifacts; it runs no scoring, live/API/model calls, and writes no secrets.
