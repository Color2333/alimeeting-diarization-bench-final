# Realtime System Regression

- Status: `pass`
- Steps: `29/29` passed
- Duration: `537.23s`
- Final DER: `16.49%`
- Best-baseline margin: `0.38858333333333384` pp
- Beats all baselines: `True`
- Self-check: `warn` (`fail=0`, `warn=4`)

## Steps

| Status | Step | Duration | Command |
|---|---|---:|---|
| `pass` | `audio_window_features` | 4.96s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_audio_window_features.py` |
| `pass` | `selector_validation` | 0.36s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/validate_guarded_slow_selector.py` |
| `pass` | `selector_policy_search` | 16.59s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/search_system_selector_policies.py` |
| `pass` | `rare_selector_overlay_search` | 2.69s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/search_rare_selector_overlay_policies.py` |
| `pass` | `slow_sanitization_search` | 43.09s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/search_slow_sanitization_policies.py` |
| `pass` | `speaker_track_sanitization_search` | 0.48s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/search_speaker_track_sanitization_policies.py` |
| `pass` | `audio_guided_sanitization_search` | 167.52s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/search_audio_guided_sanitization_policies.py` |
| `pass` | `audio_boundary_adjustment_search` | 275.32s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/search_audio_boundary_adjustment_policies.py` |
| `pass` | `all_cached_system_demo` | 3.25s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/run_realtime_diarization_system.py --all-cached-recordings --output-dir outputs/system_demo/all_cached_recordings` |
| `pass` | `realtime_batch_smoke` | 1.14s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/run_realtime_batch.py --recording-ids R8003_M8001,R8009_M8019 --output-dir outputs/realtime_batch/smoke` |
| `pass` | `realtime_batch_all_cached` | 4.70s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/run_realtime_batch.py --all-cached-recordings --output-dir outputs/realtime_batch/all_cached` |
| `pass` | `realtime_batch_consistency` | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/audit_realtime_batch_consistency.py` |
| `pass` | `timeline_integrity` | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/check_timeline_integrity.py` |
| `pass` | `clipped_baseline_audit` | 14.50s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/audit_clipped_baselines.py` |
| `pass` | `baseline_leaderboard_audit` | 0.06s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/audit_baseline_leaderboard.py` |
| `pass` | `runtime_overlay_contributions` | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/audit_runtime_overlay_contributions.py` |
| `pass` | `recording_level_stability` | 0.05s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/audit_recording_level_stability.py` |
| `pass` | `recording_balanced_overlay_search` | 0.35s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/search_recording_balanced_overlays.py` |
| `pass` | `recording_context_overlay_search` | 0.72s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/search_recording_balanced_overlays.py --previous-window-context --output-dir outputs/recording_context_overlay_search` |
| `pass` | `external_candidate_surface_search` | 0.92s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/search_external_candidate_surfaces.py` |
| `pass` | `external_candidate_source_inventory` | 0.05s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/audit_external_candidate_source_inventory.py` |
| `pass` | `external_candidate_reproduction_plan` | 0.10s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_external_candidate_reproduction_plan.py` |
| `pass` | `baseline_headroom_audit` | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/audit_baseline_headroom.py` |
| `pass` | `system_promotion_gate` | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_system_promotion_gate.py` |
| `pass` | `true_heldout_readiness` | 0.03s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/diagnose_true_heldout_readiness.py` |
| `pass` | `selector_robustness_diagnosis` | 0.03s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/diagnose_selector_robustness.py` |
| `pass` | `recording_stability_blockers` | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/diagnose_recording_stability_blockers.py` |
| `pass` | `next_experiment_queue` | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/build_research_next_experiment_queue.py` |
| `pass` | `system_self_check` | 0.04s | `/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/check_realtime_system_outputs.py` |

## Reading

- This regression is an offline replay over cached Fast/Slow outputs and derived runtime-safe artifacts.
- A `warn` self-check status is acceptable while selector robustness remains below the promotion gate; any `fail` should block metric claims.
