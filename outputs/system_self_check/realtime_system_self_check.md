# Realtime System Self Check

- Status: `warn`
- Checks: `40` pass, `4` warn, `0` fail
- Metrics: `outputs/system_demo/all_cached_recordings/metrics.json`

| Status | Code | Message |
|---|---|---|
| `pass` | `metrics_exists` | metrics.json exists and is readable |
| `pass` | `scored_with_reference` | system run is scored with cached AliMeeting reference windows |
| `pass` | `cached_window_coverage` | selected windows are fully covered by cached Fast/Slow outputs |
| `pass` | `no_live_api_calls` | offline system path performs zero live DeepSeek/Qwen/Omni calls |
| `pass` | `beats_all_baselines` | final DER beats every tracked same-window baseline |
| `pass` | `positive_best_baseline_margin` | final DER has positive margin against the best baseline |
| `pass` | `expected_default_variant` | default system variant is rare audio rule overlay on speaker-count-safe guarded fallback |
| `pass` | `base_selector_validation_matches_runtime` | selector validation covers the base fallback policy and beats Slow on the development pool |
| `warn` | `selector_robust_validation` | selector has robust bootstrap evidence; warn until this becomes true |
| `pass` | `selector_search_tracks_base_fallback_rule` | selector search identifies the speaker-count-safe guard family as the best full-pool base fallback policy |
| `pass` | `rare_selector_overlay_search_present` | rare selector overlay search artifact is present and reports a known status |
| `pass` | `rare_selector_overlay_matches_runtime` | rare selector overlay search supports the runtime stacked rare rule candidates on the development pool |
| `warn` | `rare_selector_robust_validation` | rare selector overlay has robust bootstrap/recording-holdout evidence; warn until this becomes true |
| `pass` | `slow_sanitization_search_present` | Slow sanitizer search artifact is present and reports a known status |
| `pass` | `speaker_track_sanitization_search_present` | speaker-track sanitizer search artifact is present and reports whether low-evidence speaker-track pruning is robust |
| `pass` | `speaker_track_score_cache_present` | speaker-track sanitizer search records score-cache state so repeated regression runs stay fast |
| `pass` | `audio_guided_sanitization_search_present` | audio-guided sanitizer search artifact is present and reports a known status |
| `pass` | `audio_boundary_adjustment_search_present` | audio-guided boundary adjustment search artifact is present and reports a known status |
| `pass` | `final_timeline_integrity_pass` | final timeline artifacts are internally consistent and contain no same-speaker self-overlap |
| `pass` | `beats_all_clipped_baselines` | final DER beats every tracked same-window baseline after applying the same runtime window clipping |
| `pass` | `beats_all_full_coverage_baselines` | final DER beats every discovered baseline artifact that covers the full current 120-window pool |
| `pass` | `runtime_overlay_contributions_pass` | active runtime overlays have positive clipped-Slow contribution and no negative overlay windows |
| `pass` | `headroom_audit_gap` | current final path is close to analysis-only oracle over existing candidates |
| `pass` | `promotion_gate_dev_metric_pass` | promotion gate confirms the development-pool metric beats tracked baselines |
| `warn` | `promotion_gate_generalization_pass` | promotion gate confirms robust selector evidence and true-heldout readiness; warn until this becomes true |
| `pass` | `true_heldout_readiness_present` | true-heldout readiness diagnosis exists, reports a known state, and makes no metric claim |
| `pass` | `selector_robustness_diagnosis_present` | selector robustness diagnosis explains current promotion blockers or confirms readiness |
| `pass` | `realtime_batch_smoke_pass` | manifest-style batch runner processes multiple recordings with per-item integrity checks and zero live API calls |
| `pass` | `realtime_batch_all_cached_pass` | all-cached batch runner processes every cached recording with per-item integrity checks and zero live API calls |
| `pass` | `realtime_batch_consistency_pass` | all-cached batch weighted DER matches the corpus-level all-cached system demo |
| `pass` | `recording_level_stability_present` | recording-level stability audit exists and reports final-vs-clipped-baseline resampling evidence |
| `warn` | `recording_level_stability_robust` | recording-level gain is positive across recordings with a positive recording-bootstrap lower bound; warn until this becomes true |
| `pass` | `recording_balanced_overlay_search_present` | recording-balanced overlay search exists and reports whether another deployable stability candidate remains |
| `pass` | `recording_context_overlay_search_present` | previous-window context overlay search exists and reports whether another deployable stability candidate remains |
| `pass` | `external_candidate_surface_search_present` | external candidate surface search exists and reports whether historical model outputs can create a new candidate surface |
| `pass` | `external_candidate_search_gt_filtered` | external candidate search excludes stale same-key windows whose GT fingerprint does not match the current runtime pool |
| `pass` | `external_candidate_oracle_sources_excluded` | default external candidate deployability search excludes speaker_count_mode=oracle summaries as eval-only upper bounds |
| `pass` | `external_candidate_source_inventory_present` | external candidate source inventory exists and uses GT-fingerprint filtering over the current runtime window pool |
| `pass` | `external_candidate_reproduction_plan_present` | external candidate reproduction plan exists and records the missing-window/resume gate before default runtime promotion |
| `pass` | `external_candidate_manifest_resume_command_ready` | external candidate reproduction plan exposes a manifest-only resume command with distinct summary/results filenames |
| `pass` | `external_candidate_full_refresh_command_ready` | external candidate reproduction plan also exposes a full 120-window refresh command for promotion scoring |
| `pass` | `external_candidate_missing_manifest_consistent` | missing-window manifest row count matches the reproduction-plan coverage gap |
| `pass` | `external_candidate_stale_reprocess_command_ready` | external candidate reproduction plan requires force reprocess whenever stale checkpoint windows are present |
| `pass` | `recording_stability_blockers_present` | recording stability blocker diagnosis exists and explains whether current candidate pools can improve non-positive recordings |
