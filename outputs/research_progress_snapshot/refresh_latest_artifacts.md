# Latest Research Artifact Refresh

- Status: `pass`
- Commands: `100`
- Total elapsed: `103.42s`
- PPT updated: `True`

| Step | Return | Elapsed | Command |
|---:|---:|---:|---|
| 1 | 0 | 0.05s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_timeline_review_audit.py` |
| 2 | 0 | 0.06s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_memory_update_replay.py` |
| 3 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_system_timeline_summary.py --latencies outputs/latency_tradeoff/main_models.csv --segments 120 --writeback-impact outputs/writeback_gate_120/writeback_impact_summary.json --guard-summary outputs/llm_window_batch/window_batch_summary.csv --runtime-safe-guard-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_safety_summary.json --review-audit-summary outputs/timeline_review_audit/llm_review_signal_timeline_audit_summary.json --output-csv outputs/system_timeline/system_timeline.csv --output-md outputs/system_timeline/system_timeline.md --summary-json outputs/system_timeline/summary.json` |
| 4 | 0 | 42.87s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/evaluate_rule_writeback_timeline.py --fast-summary outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json --slow-summary outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json --gate-decisions outputs/writeback_gate_120/gate_decisions.csv --patches outputs/segment_patches/sortformer_diarizen_120_patches.csv --output-dir outputs/rule_writeback_timeline_120` |
| 5 | 0 | 0.11s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/validate_recover_selector_split.py` |
| 6 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_selector_true_heldout_candidate_scan.py` |
| 7 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/validate_selector_true_heldout_split_file.py` |
| 8 | 0 | 2.14s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/bootstrap_realtime_contract_metrics.py --results outputs/rule_writeback_timeline_120/rule_writeback_timeline_results.csv --output-dir outputs/realtime_contract_bootstrap_120` |
| 9 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/analyze_realtime_contract_by_recording.py --results outputs/rule_writeback_timeline_120/rule_writeback_timeline_results.csv --output-dir outputs/realtime_contract_recording_stability_120` |
| 10 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_selector_true_heldout_protocol.py` |
| 11 | 0 | 0.47s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_omni_guard_summary.py` |
| 12 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/summarize_omni_window_batch.py outputs/omni_guard/omni_flash_plus_window_batch_12.csv` |
| 13 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/analyze_omni_acoustic_fusion.py` |
| 14 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_omni_expansion_manifest.py` |
| 15 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_omni48_live_call_manifest.py` |
| 16 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/analyze_runtime_safe_llm_latency.py` |
| 17 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/simulate_runtime_safe_llm_splitting.py` |
| 18 | 0 | 0.05s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/analyze_llm_guard_tuning.py` |
| 19 | 0 | 0.05s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/materialize_llm_guard_tuning.py` |
| 20 | 0 | 0.05s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/analyze_runtime_safe_llm_guard.py --batch-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned.jsonl --output-csv outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned_passthrough_safety.csv --output-md outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned_passthrough_safety.md --summary-json outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_tuned_passthrough_safety_summary.json --allow-keep-fast-passthrough-in-quarantine` |
| 21 | 0 | 0.06s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/materialize_tuned_writeback_gate.py` |
| 22 | 0 | 43.12s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/evaluate_rule_writeback_timeline.py --fast-summary outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json --slow-summary outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json --gate-decisions outputs/runtime_safe_llm_window_batch/tuned_v2_writeback_gate_decisions.csv --patches outputs/segment_patches/sortformer_diarizen_120_patches.csv --output-dir outputs/runtime_safe_llm_window_batch/tuned_v2_writeback_timeline` |
| 23 | 0 | 0.28s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/audit_runtime_evidence_contract.py` |
| 24 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_der_latency_pareto.py` |
| 25 | 0 | 0.06s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_system_experiment_matrix.py` |
| 26 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_runtime_latency_budget_ledger.py` |
| 27 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_stage_latency_slo_audit.py` |
| 28 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_research_progress_snapshot.py` |
| 29 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_research_claims_manifest.py` |
| 30 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_runtime_replay_manifest.py` |
| 31 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_split20_full_live_manifest.py` |
| 32 | 0 | 0.55s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_split20_resume_export_audit.py` |
| 33 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_split_policy_optimization.py` |
| 34 | 0 | 0.40s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_split15_stretch_reexport_audit.py` |
| 35 | 0 | 0.05s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_run_readiness.py` |
| 36 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_agent_execution_plan.py` |
| 37 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_postrun_metrics_closure.py` |
| 38 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_output_audit.py` |
| 39 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_scoring_readiness.py` |
| 40 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_input_integrity_audit.py` |
| 41 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_execution_runbook.py` |
| 42 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_command_surface_audit.py` |
| 43 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_output_repair_plan.py` |
| 44 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/run_live_execution_sequence.py` |
| 45 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_execution_receipt_audit.py` |
| 46 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_resume_state_audit.py` |
| 47 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_runtime_environment_audit.py` |
| 48 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_execution_timing_plan.py` |
| 49 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_retry_budget_audit.py` |
| 50 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_token_quota_budget_audit.py` |
| 51 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_parallelism_sensitivity.py` |
| 52 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_failure_recovery_playbook.py` |
| 53 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_research_next_experiment_queue.py` |
| 54 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_claim_promotion_gate.py` |
| 55 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_metric_extraction_contract.py` |
| 56 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_output_schema_contract.py` |
| 57 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_latency_risk_margin_audit.py` |
| 58 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_acceptance_scorecard.py` |
| 59 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_execution_handoff_packet.py` |
| 60 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_latency_claim_matrix.py` |
| 61 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_scoring_execution_plan.py` |
| 62 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/run_post_live_scoring_sequence.py` |
| 63 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_scoring_output_audit.py` |
| 64 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_evidence_dependency_dag.py` |
| 65 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_execution_bundle.py` |
| 66 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_time_metric_statistics_plan.py` |
| 67 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_time_metric_extractor.py` |
| 68 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_promotion_preflight_audit.py` |
| 69 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_scoring_receipt_audit.py` |
| 70 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_time_metric_receipt_audit.py` |
| 71 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_claim_promotion_receipt_audit.py` |
| 72 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_execution_eligibility_gate.py` |
| 73 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_latency_risk_mitigation_plan.py` |
| 74 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_phase_result_scorecard.py` |
| 75 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_provider_routing_decision.py` |
| 76 | 0 | 9.75s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/update_progress_pptx_latest_results.py` |
| 77 | 0 | 0.14s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_report_ppt_traceability.py` |
| 78 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/run_live_execution_sequence.py` |
| 79 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_execution_receipt_audit.py` |
| 80 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_claim_promotion_gate.py` |
| 81 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_latency_risk_margin_audit.py` |
| 82 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_acceptance_scorecard.py` |
| 83 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_execution_handoff_packet.py` |
| 84 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_latency_claim_matrix.py` |
| 85 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_scoring_execution_plan.py` |
| 86 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/run_post_live_scoring_sequence.py` |
| 87 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_scoring_output_audit.py` |
| 88 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_evidence_dependency_dag.py` |
| 89 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_execution_bundle.py` |
| 90 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_time_metric_statistics_plan.py` |
| 91 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_time_metric_extractor.py` |
| 92 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_promotion_preflight_audit.py` |
| 93 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_scoring_receipt_audit.py` |
| 94 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_time_metric_receipt_audit.py` |
| 95 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_post_live_claim_promotion_receipt_audit.py` |
| 96 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_execution_eligibility_gate.py` |
| 97 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_latency_risk_mitigation_plan.py` |
| 98 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_phase_result_scorecard.py` |
| 99 | 0 | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_live_provider_routing_decision.py` |
| 100 | 0 | 0.15s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/validate_latest_research_artifacts.py` |

## Reading

- This refresh rebuilds derived analysis/reporting artifacts from existing experiment outputs.
- It does not run new model inference or live LLM/API calls.
- Use it before updating the report deck to keep timeline, memory replay, selector validation, selector true-heldout candidate scan, selector true-heldout split validation, selector true-heldout protocol, Omni fusion, Omni expansion manifest, Omni48 call manifest, LLM guard latency, split simulation, split20 full-live manifest, split20 resume export audit, split policy optimization, tuning/materialization, Pareto, runtime-audit, matrix, latency budget ledger, latency SLO audit, latency risk margin audit, latency risk mitigation plan, snapshot, claims manifest, runtime replay manifest, live-run readiness, live Agent execution plan, live postrun metrics closure, live output audit, live scoring readiness, live input integrity audit, live execution runbook, live command surface audit, live execution eligibility gate, live execution receipt audit, live resume state audit, live runtime environment audit, live execution timing plan, live retry budget audit, live token/quota budget audit, live parallelism sensitivity, next-experiment queue, post-live claim promotion gate, post-live scoring output audit, post-live promotion preflight audit, post-live scoring receipt audit, post-live time metric receipt audit, post-live claim promotion receipt audit, phase result scorecard, live provider routing decision, report/PPT traceability, and validation numbers aligned.
