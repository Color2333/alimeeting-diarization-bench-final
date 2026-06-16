# Report/PPT Traceability

- Runtime contract: `report_ppt_traceability_from_existing_artifacts_no_live_calls`
- Status: `pass`
- Rows: `54`
- Fully covered rows: `54`
- Missing report rows: `0`
- Missing PPT rows: `0`
- Missing source rows: `0`
- Live calls performed by builder: `0`
- No new metric claim: `True`

## Matrix

| Trace | Topic | Expected value | Boundary | Source | Report | PPT |
|---|---|---|---|---|---|---|
| `phase_result_scorecard` | Phase result scorecard | results 8; SLO 4/4 | `phase_scorecard_no_live_or_scoring_calls` | `True` | `True` | `True` |
| `live_provider_routing_decision` | Live provider routing decision | default none; deepseek no-go True | `provider_route_blocks_default_deepseek_execute` | `True` | `True` | `True` |
| `latency_budget_ledger` | Runtime latency budget ledger | claim-now rows 4 | `claim_now_only` | `True` | `True` | `True` |
| `stage_latency_slo_audit` | Stage latency SLO audit | claim-now SLO 4/4 | `no_new_metric_claim` | `True` | `True` | `True` |
| `latency_risk_margin_audit` | Latency risk margin audit | tight 1 / guard tight_margin | `risk_label_no_new_metric_claim` | `True` | `True` | `True` |
| `latency_risk_mitigation_plan` | Latency risk mitigation plan | primary max20 / stretch max15 | `mitigation_plan_no_new_metric_claim` | `True` | `True` | `True` |
| `selector_candidate_scan` | Selector true-heldout candidate scan | eligible 0 / missing 8 | `no_metric_claim` | `True` | `True` | `True` |
| `selector_split_validation` | Selector true-heldout split validation | true-heldout recordings 0 | `blocked_waiting_for_valid_sealed_split` | `True` | `True` | `True` |
| `selector_protocol` | Selector true-heldout protocol | sealed split required before scoring | `protocol_only_no_metric_claim` | `True` | `True` | `True` |
| `omni48_call_manifest` | Omni48 call manifest | 48 windows / 96 calls | `pending_live_label_only` | `True` | `True` | `True` |
| `split20_manifest` | Split20 full-live manifest | 104 parents / 147 calls / resume 139 | `blocked_by_provider_quota_or_capacity` | `True` | `True` | `True` |
| `split20_resume_export_audit` | Split20 resume export audit | 139 prompts / 101 parents | `export_only_no_live_calls` | `True` | `True` | `True` |
| `split15_stretch_reexport_audit` | Split15 stretch re-export audit | 178 prompts / 104 parents | `stretch_export_only_no_live_calls` | `True` | `True` | `True` |
| `split_policy_optimization` | Split policy optimization | primary max20 / stretch max15 | `no_metric_claim` | `True` | `True` | `True` |
| `live_readiness` | Live readiness | 0/3 ready | `non_secret_no_live_calls` | `True` | `True` | `True` |
| `live_agent_plan` | Live Agent execution plan | 382 planned live calls | `handoff_plan_no_live_calls` | `True` | `True` | `True` |
| `live_execution_runbook` | Live execution runbook | 7 steps / P0 calls 139 | `no_secret_values_no_live_calls` | `True` | `True` | `True` |
| `live_execution_bundle` | Live execution bundle | bundle 8 / live calls 382 | `execution_bundle_no_live_calls_no_secret_values` | `True` | `True` | `True` |
| `live_execution_handoff_packet` | Live execution handoff packet | packet 7 / P0 5 | `live_execution_handoff_no_live_calls_no_secret_values` | `True` | `True` | `True` |
| `live_command_surface_audit` | Live command surface audit | ready 3/3 commands | `command_surface_no_live_calls_no_secret_values` | `True` | `True` | `True` |
| `live_execution_launcher` | Live execution launcher | selected 139 / available 382 | `launcher_dry_run_no_live_calls_execute_live_requires_flag` | `True` | `True` | `True` |
| `live_execution_eligibility_gate` | Live execution eligibility gate | pass 2 / blocked 5 | `live_execution_eligibility_no_live_calls` | `True` | `True` | `True` |
| `live_execution_receipt_audit` | Live execution receipt audit | record False / started 0 | `live_execution_receipt_no_live_calls` | `True` | `True` | `True` |
| `live_output_repair_plan` | Live output repair plan | repair 3 / missing 382 | `repair_plan_no_live_or_scoring_calls` | `True` | `True` | `True` |
| `live_resume_state_audit` | Live resume state audit | clean 3/3 surfaces | `resume_state_no_live_calls_no_metric_claim` | `True` | `True` | `True` |
| `live_runtime_environment_audit` | Live runtime environment audit | checks 14/14 | `runtime_env_no_live_calls_no_secret_values` | `True` | `True` | `True` |
| `live_execution_timing_plan` | Live execution timing plan | deepseek 139 calls / 384.444s | `timing_plan_no_live_metric_claim` | `True` | `True` | `True` |
| `live_retry_budget_audit` | Live retry budget audit | max requests 764 / P0 278 | `retry_budget_no_live_metric_claim` | `True` | `True` | `True` |
| `live_token_quota_budget_audit` | Live token quota budget audit | llm retry token proxy 1658856 / P0 801724 | `token_quota_budget_no_live_metric_claim` | `True` | `True` | `True` |
| `live_failure_recovery_playbook` | Live failure recovery playbook | scenarios 8 / current blockers 5 | `failure_recovery_no_live_metric_claim` | `True` | `True` | `True` |
| `live_metric_extraction_contract` | Live metric extraction contract | metrics 8 / time 3 | `metric_extraction_schema_no_live_metric_claim` | `True` | `True` | `True` |
| `live_output_schema_contract` | Live output schema contract | schemas 8 / fields 62 | `output_schema_no_live_metric_claim` | `True` | `True` | `True` |
| `post_live_acceptance_scorecard` | Post-live acceptance scorecard | scorecard 9 / blocked 6 | `acceptance_scorecard_no_live_metric_claim` | `True` | `True` | `True` |
| `post_live_latency_claim_matrix` | Post-live latency claim matrix | latency claims 8 / claim-now 4 | `latency_claim_matrix_no_live_metric_claim` | `True` | `True` | `True` |
| `post_live_time_metric_statistics_plan` | Post-live time metric statistics plan | time stats 9 / blocked 5 | `time_statistics_plan_no_live_or_scoring_calls` | `True` | `True` | `True` |
| `post_live_time_metric_extractor` | Post-live time metric extractor | extractor 3 / ready 0 | `time_metric_extractor_no_live_or_scoring_calls` | `True` | `True` | `True` |
| `post_live_time_metric_receipt_audit` | Post-live time metric receipt audit | pass 1 / rows 6 | `time_metric_receipt_no_live_or_scoring_calls` | `True` | `True` | `True` |
| `post_live_scoring_execution_plan` | Post-live scoring execution plan | scoring steps 6 / P0 3 | `scoring_execution_plan_no_live_or_scoring_calls` | `True` | `True` | `True` |
| `post_live_scoring_launcher` | Post-live scoring launcher | ready 0 / executed 0 | `scoring_launcher_dry_run_no_scoring_calls` | `True` | `True` | `True` |
| `post_live_scoring_receipt_audit` | Post-live scoring receipt audit | record False / executed 0 | `scoring_receipt_no_live_or_scoring_calls` | `True` | `True` | `True` |
| `post_live_scoring_output_audit` | Post-live scoring output audit | outputs ready 0 / rows 6 | `scoring_output_audit_no_scoring_calls` | `True` | `True` | `True` |
| `post_live_evidence_dependency_dag` | Post-live evidence dependency DAG | dag 10 / blocked 10 | `evidence_dependency_dag_no_live_or_scoring_calls` | `True` | `True` | `True` |
| `post_live_promotion_preflight_audit` | Post-live promotion preflight audit | blocked 4 / ready 0 | `promotion_preflight_no_live_or_scoring_calls` | `True` | `True` | `True` |
| `live_parallelism_sensitivity` | Live parallelism sensitivity | max20 / 8 workers | `parallelism_plan_no_live_metric_claim` | `True` | `True` | `True` |
| `live_postrun_closure` | Live postrun metrics closure | DeepSeek success 8; Omni48 success 0 | `pending_live_outputs` | `True` | `True` | `True` |
| `live_output_audit` | Live output audit | missing surfaces 3 | `blocked_missing_output` | `True` | `True` | `True` |
| `live_scoring_readiness` | Live scoring readiness | ready 0/5 | `blocked_waiting_live_outputs` | `True` | `True` | `True` |
| `live_input_integrity_audit` | Live input integrity audit | ready 3/3 | `input_integrity_no_live_metric_claim` | `True` | `True` | `True` |
| `post_live_claim_promotion_gate` | Post-live claim promotion gate | ready 0 / gates 8 | `promote_only_after_output_audit_scoring_slo_and_traceability_pass` | `True` | `True` | `True` |
| `post_live_claim_promotion_receipt_audit` | Post-live claim promotion receipt audit | pass 3 / rows 6 | `claim_promotion_receipt_no_claim_writes` | `True` | `True` | `True` |
| `runtime_replay_manifest` | Runtime replay manifest | 6 runtime stages | `writeback_right_explicit` | `True` | `True` | `True` |
| `memory_update_replay` | Memory update replay | 4 review cases blocked from memory update | `memory_only_no_timeline_rollback` | `True` | `True` | `True` |
| `claims_manifest` | Claims manifest | 12 claims with source artifacts and validation checks | `claim_strength_explicit` | `True` | `True` | `True` |
| `next_experiment_queue` | Next experiment queue | P0 split20 + true-heldout | `future_work_queue` | `True` | `True` | `True` |

## Reading

- This matrix checks that report and PPT surfaces mention the same evidence artifacts and claim boundaries.
- It reads existing artifacts, report markdown, and PPT text only; it performs no live/API/model calls.
- Rows marked pending or blocked remain traceability rows, not promoted metric claims.
