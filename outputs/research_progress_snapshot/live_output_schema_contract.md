# Live Output Schema Contract

- Runtime contract: `live_output_schema_contract_no_live_calls`
- Status: `blocked_waiting_live_outputs`
- Schema contracts: `8`
- P0 schema contracts: `5`
- Live output schema contracts: `3`
- Scoring output schema contracts: `3`
- Required fields: `62`
- Expected live output rows: `382`
- Missing output surfaces: `3`
- Ready to score: `0`
- Live calls performed by builder: `0`
- No new metric claim: `True`

| Schema | Stage | Surface | Priority | Expected rows | Required fields | Claim status |
|---|---|---|---|---:|---|---|
| `deepseek_resume_llm_success_jsonl` | `live_output_jsonl` | `deepseek_resume_after_top3` | `P0` | 139 | window_id; parent_window_id; window_decision; patch_decisions; call_seconds; total_tokens; call_attempts; max_call_attempts | `required_before_deepseek_safety_and_latency_scoring` |
| `qwen_full_llm_success_jsonl` | `live_output_jsonl` | `qwen_full_backup` | `P1` | 147 | window_id; parent_window_id; window_decision; patch_decisions; call_seconds; total_tokens; call_attempts; max_call_attempts | `fallback_only_required_before_qwen_scoring` |
| `omni48_success_jsonl` | `live_output_jsonl` | `omni48_label_only` | `P1` | 96 | call_id; window_id; recording_id; model; bucket; diarization_risk; should_quarantine; should_defer_to_slow_agent; call_seconds; call_attempts; max_call_attempts; schema_ok | `label_only_required_before_omni48_metric_scoring` |
| `bounded_retry_error_row` | `live_output_error_row` | `all_live_surfaces` | `P0` | 382 | error; call_attempts; max_call_attempts; retry_backoff_seconds; window_id_or_call_id | `records_failed_attempts_without_metric_promotion` |
| `llm_safety_summary` | `scoring_output_summary` | `llm_split20_surfaces` | `P0` | 2 | harmful_accepts; conservative_blocks; missing_patch_eval; parent_window_decision_override; avg_call_seconds; p95_call_seconds; p95_correction_delay_seconds | `required_before_zero_harm_safety_claim` |
| `split20_comparison_summary` | `scoring_output_summary` | `deepseek_resume_after_top3` | `P0` | 147 | parent_windows; split_calls; original_max_call_seconds; split_max_call_seconds; split_parent_avg_max_call_seconds; token_multiplier; harmful_accepts; parent_window_decision_override | `required_before_full_split20_latency_claim` |
| `omni48_metric_summary` | `scoring_output_summary` | `omni48_label_only` | `P1` | 96 | model; windows; high_positive_rate; clean_false_positive_rate; quarantines; defers; avg_call_seconds; p95_call_seconds; max_call_seconds | `label_only_no_timeline_writeback` |
| `promotion_traceability_summary` | `promotion_output_summary` | `all_live_surfaces` | `P0` | 8 | ready_to_promote_count; traceability_rows; fully_covered_rows; missing_source_rows; no_new_metric_claim | `required_before_report_ppt_claim_promotion` |

## Reading

- This contract defines the field-level interface between live outputs, scoring scripts, metric extraction, and promotion gates.
- Missing live outputs are not schema-validated yet; the current rows are a preflight schema contract for future validation.
- LLM and Omni live output fields must be present before scoring readiness can move from blocked to ready.
- The builder only reads local artifacts; it performs no live/API/model/scoring calls and writes no secrets.
