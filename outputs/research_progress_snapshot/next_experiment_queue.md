# Research Next Experiment Queue

- Runtime contract: `research_next_experiment_queue_from_validated_claims`
- Can claim now: `7`
- Next experiments: `6`
- P0 experiments: `3`
- Blocked experiments: `1`
- Ready experiments: `1`
- Prepared experiments: `1`
- Completed experiments: `2`
- Do-not-deploy items: `1`

## Can Claim Now

| Claim ID | Contract | Writeback right | Claim |
|---|---|---|---|
| `four_stage_realtime_route` | `runtime_pass` | `fast_first_output_and_rule_writeback_only` | Fast first output arrives at 0.38s, rule writeback at 24.65s, LLM guard at 44.92s, and LLM review at 46.10s. |
| `runtime_evidence_contract_clean` | `runtime_pass` | `contract_audit_only` | Runtime evidence audit is pass with 16 artifacts and 0 runtime-blocking artifacts. |
| `rule_writeback_primary_correction` | `runtime_pass` | `bounded_timeline_writeback` | Rule writeback applies 599 patches and recovers 60.2% of Fast miss (197.36s unique miss seconds). |
| `runtime_safe_llm_guard_zero_harm` | `runtime_pass` | `block_or_quarantine_only` | Runtime-safe LLM guard covers 104 windows / 1917 patches with harmful accept 0, average delay 44.92s and P95 63.85s. |
| `guard_tuning_passthrough_safe` | `runtime_pass_with_passthrough_exception` | `keep_fast_supported_passthrough_exception` | Guard tuning policy combined_review0.5_keepfast0.5 recovers 260 conservative blocks; materialized safe 323 / harmful 0. |
| `llm_review_memory_not_timeline` | `runtime_pass` | `memory_protection_only` | LLM review has 4 cases, blocks timeline writeback 0, and blocks memory update 4 at arrival 46.10s. |
| `voiceprint_rule_handles_clean_high` | `runtime_candidate_gate` | `rule_auto_for_clean_high` | Voiceprint gate has 620/620 clean patches with voiceprint, 226 high bucket, 138 high rule-auto, and 0 LLM candidates. |

## Next Experiments

| Experiment | Priority | Status | Target claim | Current evidence | Success gates |
|---|---|---|---|---|---|
| `full_split20_live_104w` | `P0` | `blocked_by_deepseek_top4_5_quota` | `split20_latency_path_limited` | top3 live wall 29.01s vs original max 48.47s; harmful 0; deepseek top4/5 AllocationQuota.FreeTierOnly; readiness blocked_by_provider_quota_or_capacity; manifest resume calls 139; Agent plan calls 382; postrun closure blocked_by_quota_or_missing_resume; output audit missing 3 surfaces; scoring readiness P0 steps 2; split policy primary max20 vs stretch max15; runbook steps 7. | Run all 104 parent windows with split<=20 live parallel calls.<br>Keep effective harmful_accepts at 0 after runtime-safe quarantine override.<br>Show measured wall-time improvement over unsplit max-call baseline on the full surface.<br>Record token multiplier and provider failure rate. |
| `true_heldout_selector_recordings` | `P0` | `needs_new_recording_split` | `selector_generalization_positive` | recording holdout 8/8 positive; heldout DER 26.5% vs Fast 28.6%; bootstrap delta 2.2%; protocol needs_new_recording_split; candidate scan eligible 0 / missing 8; sealed split validation blocked_waiting_for_valid_sealed_split. | Use recordings not involved in threshold selection.<br>Keep weighted DER below Fast and below rule writeback fallback.<br>Report DER/Miss/FA/Conf plus arrival latency for each recording.<br>Keep all selector prompt/runtime surfaces free of DER, GT support, and oracle labels. |
| `new_candidate_surface_for_non_positive_recordings` | `P0` | `ready_to_design_from_blocker_audit` | `recording_level_stability_positive` | recording stability blocker status candidate_pool_exhausted_for_non_positive_recordings; non-positive recordings 3/8; non-positive candidate-pool oracle gain 0.0pp; global candidate oracle gap 0.012833333333333273pp; full baseline leaderboard 8 baselines, beats all True; external candidate surface external_candidate_surface_not_deployable with best delta 0.00016666666666498298pp, coverage 120 windows, positive recordings 7/8; reproduction plan ready_for_default_runtime_promotion_check, missing 0 windows, resume supported True. | Create at least one new runtime-eligible candidate timeline for R8001_M8004, R8008_M8013, or R8009_M8020.<br>Use prediction/audio/runtime features only; do not use DER, GT speaker labels, oracle support, or evaluation-only abnormal flags at selection time.<br>Show candidate-level clipped DER improves at least one currently non-positive recording without adding negative overlay windows elsewhere.<br>Promote to default runtime only after all-cached DER still beats the full-coverage baseline leaderboard and recording-level stability improves. |
| `omni_fusion_expand_48_or_120` | `P1` | `prepared_manifest_pending_live_calls` | `omni_fusion_label_only` | 12 windows; high sentinel recall 1/4 (25.0%); clean sentinel FP 0/4 (0.0%); review FP 4/4 (100.0%); expansion manifest 48 windows; readiness blocked_missing_credentials; Agent plan label-only calls 96; postrun closure pending_omni48_live_outputs; output audit claim-ready 0 surfaces; scoring readiness blocked 5 steps. | Expand to at least 48 windows, preferably 120.<br>Keep Omni output label-only with no timeline writeback.<br>Separate high sentinel precision/recall from ordinary review hint false positives.<br>Report first text latency, total latency, and acoustic-fusion arrival time. |
| `memory_update_audit_replay` | `P1` | `completed_validated_artifact` | `llm_review_memory_not_timeline` | 4 review cases; timeline writeback blocks 0; memory update blocks 4; replay blocked 4. | Replay all review/defer/repeatability-drift cases through the memory update gate.<br>Show memory updates are blocked without changing timeline writeback.<br>Emit before/after memory candidate counts and blocked reasons.<br>Keep prompt/runtime surface free of GT and DER fields. |
| `end_to_end_runtime_replay_manifest` | `P1` | `completed_validated_artifact` | `runtime_evidence_contract_clean` | runtime evidence audit pass; 16 artifacts; blocking 0; replay stages 6. | Emit one manifest row per stage: Fast, Rule, LLM guard, LLM review, Omni label, memory gate.<br>For each row, include arrival time, writeback right, source artifact, and validation check.<br>Verify no runtime row references DER, GT support, oracle labels, or eval-only abnormal flags.<br>Keep report/PPT derived from this manifest or explicitly linked to it. |

## Do Not Deploy

| Item | Source claim | Reason |
|---|---|---|
| `boundary_auto_writeback` | `boundary_auto_writeback_negative_control` | negative-control DER 33.8% vs recover-best 26.4%; claim strength is do_not_deploy. |
