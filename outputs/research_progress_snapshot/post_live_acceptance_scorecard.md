# Post-Live Acceptance Scorecard

- Runtime contract: `post_live_acceptance_scorecard_no_live_calls`
- Status: `blocked_waiting_live_outputs`
- Scorecard rows: `9`
- P0 rows: `6`
- Blocked rows: `6`
- Fallback-only rows: `1`
- Claim-now SLO pass: `4/4`
- Guard P95 margin seconds: `1.151`
- Expected live calls: `382`
- Missing output surfaces: `3`
- Ready to score: `0`
- Metric contracts: `8`
- Schema contracts: `8`
- Ready to promote: `0`
- Live calls performed by builder: `0`
- No new metric claim: `True`

| Scorecard | Surface | Priority | Area | Status | Pass condition | Claim effect |
|---|---|---|---|---|---|---|
| `current_claim_now_slo_preserve` | `current_claim_now_surfaces` | `P0` | `current_latency_slo` | `preserve_pass` | claim_now_slo_pass == claim_now_slo_rows == 4 and failed_claim_rows is empty | preserve current report/PPT latency claims while post-live surfaces remain blocked |
| `deepseek_resume_output_coverage` | `deepseek_resume_after_top3` | `P0` | `output_coverage` | `blocked_missing_output` | 139 successful resume rows, 101 parent windows, zero parse errors, zero duplicate/extra/missing call ids | unblocks P0 DeepSeek safety and comparison scoring |
| `deepseek_resume_output_schema` | `deepseek_resume_after_top3` | `P0` | `output_schema` | `blocked_missing_output` | LLM success JSONL fields include window_id, parent_window_id, window_decision, patch_decisions, call_seconds, total_tokens, call_attempts, max_call_attempts | prevents incomplete output rows from entering safety or latency scoring |
| `deepseek_resume_safety_zero_harm` | `deepseek_resume_after_top3` | `P0` | `safety_scoring` | `blocked_waiting_live_output` | harmful_accepts == 0, missing_patch_eval == 0, parent_window_decision_override is true | enables DeepSeek split20 zero-harm safety claim after output coverage passes |
| `deepseek_split20_latency_evidence` | `deepseek_resume_after_top3` | `P0` | `latency_scoring` | `blocked_waiting_live_output` | 104 parent windows, 147 split calls, split comparison summary present, harmful_accepts == 0, traceability covered | can promote split20 from top3 smoke/planning into full-surface latency evidence |
| `omni48_output_schema` | `omni48_label_only` | `P1` | `omni_output_schema` | `blocked_missing_output` | 96 Omni rows, 48 windows, schema_ok true, call_id/model/risk/quarantine/latency/retry fields present | unblocks Omni48 label-only scoring without timeline writeback |
| `omni48_label_metrics` | `omni48_label_only` | `P1` | `omni_label_scoring` | `blocked_waiting_live_output` | high_positive_rate, clean_false_positive_rate, quarantines, defers, avg/P95/max call latency reported for both models | promotes Omni48 label-only metrics while preserving no timeline writeback |
| `qwen_backup_fallback_boundary` | `qwen_full_backup` | `P1` | `fallback_boundary` | `fallback_only` | full backup output and scoring can be reported only as fallback unless promotion gate changes primary boundary | keeps Qwen out of primary latency claim by default |
| `report_ppt_promotion_sync` | `report_ppt` | `P0` | `traceability_sync` | `preserve_pass` | traceability fully covered rows == traceability rows and latest_artifact_validation passes after any promotion | ensures report and PPT show promoted, fallback-only, and blocked surfaces consistently |

## Reading

- This scorecard is the post-live acceptance entrypoint after output audit, schema contract, scoring readiness, and metric extraction.
- Preserve rows keep current reportable claims; blocked rows cannot be promoted until live outputs and scoring artifacts exist.
- Qwen remains fallback-only unless a future promotion gate explicitly changes its claim boundary.
- The builder only reads local artifacts; it performs no live/API/model/scoring calls and writes no secrets.
