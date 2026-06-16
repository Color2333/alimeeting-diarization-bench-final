# Research Next Experiment Queue

- Runtime contract: `research_next_experiment_queue_from_validated_claims`
- Can claim now: `0`
- Next experiments: `6`
- P0 experiments: `3`
- Blocked experiments: `1`
- Ready experiments: `4`
- Prepared experiments: `0`
- Completed experiments: `0`
- Do-not-deploy items: `1`

## Can Claim Now

| Claim ID | Contract | Writeback right | Claim |
|---|---|---|---|

## Next Experiments

| Experiment | Priority | Status | Target claim | Current evidence | Success gates |
|---|---|---|---|---|---|
| `full_split20_live_104w` | `P0` | `blocked_by_deepseek_top4_5_quota` | `split20_latency_path_limited` | top3 live wall n/a vs original max n/a; harmful 0; deepseek top4/5 n/a; readiness not_built; manifest resume calls n/a; Agent plan calls n/a; postrun closure not_built; output audit missing n/a surfaces; scoring readiness P0 steps n/a; split policy primary n/a vs stretch n/a; runbook steps n/a. | Run all 104 parent windows with split<=20 live parallel calls.<br>Keep effective harmful_accepts at 0 after runtime-safe quarantine override.<br>Show measured wall-time improvement over unsplit max-call baseline on the full surface.<br>Record token multiplier and provider failure rate. |
| `true_heldout_selector_recordings` | `P0` | `needs_new_recording_split` | `selector_generalization_positive` | recording holdout 0/0 positive; heldout DER n/a vs Fast n/a; bootstrap delta n/a; protocol not_built; candidate scan eligible n/a / missing n/a; sealed split validation not_built. | Use recordings not involved in threshold selection.<br>Keep weighted DER below Fast and below rule writeback fallback.<br>Report DER/Miss/FA/Conf plus arrival latency for each recording.<br>Keep all selector prompt/runtime surfaces free of DER, GT support, and oracle labels. |
| `new_candidate_surface_for_non_positive_recordings` | `P0` | `ready_to_design_from_blocker_audit` | `recording_level_stability_positive` | recording stability blocker status candidate_pool_exhausted_for_non_positive_recordings; non-positive recordings 3/8; non-positive candidate-pool oracle gain 0.0pp; global candidate oracle gap 0.012833333333333273pp; full baseline leaderboard 8 baselines, beats all True; external candidate surface external_candidate_surface_not_deployable with best delta 0.00016666666666498298pp, coverage 120 windows, positive recordings 7/8; reproduction plan ready_for_default_runtime_promotion_check, missing 0 windows, resume supported True. | Create at least one new runtime-eligible candidate timeline for R8001_M8004, R8008_M8013, or R8009_M8020.<br>Use prediction/audio/runtime features only; do not use DER, GT speaker labels, oracle support, or evaluation-only abnormal flags at selection time.<br>Show candidate-level clipped DER improves at least one currently non-positive recording without adding negative overlay windows elsewhere.<br>Promote to default runtime only after all-cached DER still beats the full-coverage baseline leaderboard and recording-level stability improves. |
| `omni_fusion_expand_48_or_120` | `P1` | `ready_to_run_from_existing_audio` | `omni_fusion_label_only` | 0 windows; high sentinel recall n/a; clean sentinel FP n/a; review FP n/a; expansion manifest n/a windows; readiness not_built; Agent plan label-only calls n/a; postrun closure not_built; output audit claim-ready n/a surfaces; scoring readiness blocked n/a steps. | Expand to at least 48 windows, preferably 120.<br>Keep Omni output label-only with no timeline writeback.<br>Separate high sentinel precision/recall from ordinary review hint false positives.<br>Report first text latency, total latency, and acoustic-fusion arrival time. |
| `memory_update_audit_replay` | `P1` | `ready_to_replay_from_existing_cases` | `llm_review_memory_not_timeline` | 4 review cases; timeline writeback blocks 0; memory update blocks 4; replay blocked n/a. | Replay all review/defer/repeatability-drift cases through the memory update gate.<br>Show memory updates are blocked without changing timeline writeback.<br>Emit before/after memory candidate counts and blocked reasons.<br>Keep prompt/runtime surface free of GT and DER fields. |
| `end_to_end_runtime_replay_manifest` | `P1` | `ready_to_build_from_existing_artifacts` | `runtime_evidence_contract_clean` | runtime evidence audit unknown; 0 artifacts; blocking 0; replay stages n/a. | Emit one manifest row per stage: Fast, Rule, LLM guard, LLM review, Omni label, memory gate.<br>For each row, include arrival time, writeback right, source artifact, and validation check.<br>Verify no runtime row references DER, GT support, oracle labels, or eval-only abnormal flags.<br>Keep report/PPT derived from this manifest or explicitly linked to it. |

## Do Not Deploy

| Item | Source claim | Reason |
|---|---|---|
| `boundary_auto_writeback` | `boundary_auto_writeback_negative_control` | negative-control DER n/a vs recover-best n/a; claim strength is do_not_deploy. |
