# Realtime System Regression

- Status: `pass`
- Steps: `29/29` passed
- Duration: `608.08s`
- Final DER: `16.49%`
- Best-baseline margin: `0.38858333333333384` pp
- Beats all baselines: `True`
- Self-check: `warn` (`fail=0`, `warn=4`)

## Steps

| Status | Step | Duration | Command |
|---|---|---:|---|
| `pass` | `audio_window_features` | 4.98s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.build_audio_window_features` |
| `pass` | `selector_validation` | 0.35s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.validate_guarded_slow_selector` |
| `pass` | `selector_policy_search` | 16.42s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.search_system_selector_policies` |
| `pass` | `rare_selector_overlay_search` | 2.56s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.search_rare_selector_overlay_policies` |
| `pass` | `slow_sanitization_search` | 44.94s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.search_slow_sanitization_policies` |
| `pass` | `speaker_track_sanitization_search` | 0.51s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.search_speaker_track_sanitization_policies` |
| `pass` | `audio_guided_sanitization_search` | 174.06s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.search_audio_guided_sanitization_policies` |
| `pass` | `audio_boundary_adjustment_search` | 334.30s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.search_audio_boundary_adjustment_policies` |
| `pass` | `all_cached_system_demo` | 3.85s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.realtime_system --all-cached-recordings --output-dir outputs/system_demo/all_cached_recordings` |
| `pass` | `realtime_batch_smoke` | 1.75s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.realtime_batch --recording-ids R8003_M8001,R8009_M8019 --output-dir outputs/realtime_batch/smoke` |
| `pass` | `realtime_batch_all_cached` | 5.12s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.realtime_batch --all-cached-recordings --output-dir outputs/realtime_batch/all_cached` |
| `pass` | `realtime_batch_consistency` | 0.05s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.audit_realtime_batch_consistency` |
| `pass` | `timeline_integrity` | 0.05s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.timeline_integrity` |
| `pass` | `clipped_baseline_audit` | 16.12s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.audit_clipped_baselines` |
| `pass` | `baseline_leaderboard_audit` | 0.17s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.audit_baseline_leaderboard` |
| `pass` | `runtime_overlay_contributions` | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.audit_runtime_overlay_contributions` |
| `pass` | `recording_level_stability` | 0.06s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.audit_recording_level_stability` |
| `pass` | `recording_balanced_overlay_search` | 0.41s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.search_recording_balanced_overlays` |
| `pass` | `recording_context_overlay_search` | 0.79s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.search_recording_balanced_overlays --previous-window-context --output-dir outputs/recording_context_overlay_search` |
| `pass` | `external_candidate_surface_search` | 1.03s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.search_external_candidate_surfaces` |
| `pass` | `external_candidate_source_inventory` | 0.09s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.audit_external_candidate_source_inventory` |
| `pass` | `external_candidate_reproduction_plan` | 0.13s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.build_external_candidate_reproduction_plan` |
| `pass` | `baseline_headroom_audit` | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.audit_baseline_headroom` |
| `pass` | `system_promotion_gate` | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.build_system_promotion_gate` |
| `pass` | `true_heldout_readiness` | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.diagnose_true_heldout_readiness` |
| `pass` | `selector_robustness_diagnosis` | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.diagnose_selector_robustness` |
| `pass` | `recording_stability_blockers` | 0.05s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.diagnose_recording_stability_blockers` |
| `pass` | `next_experiment_queue` | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.build_research_next_experiment_queue` |
| `pass` | `system_self_check` | 0.05s | `/opt/homebrew/opt/python@3.11/bin/python3.11 -m alimeeting_diarization_bench.final.self_check` |

## Reading

- This regression is an offline replay over cached Fast/Slow outputs and derived runtime-safe artifacts.
- A `warn` self-check status is acceptable while selector robustness remains below the promotion gate; any `fail` should block metric claims.
