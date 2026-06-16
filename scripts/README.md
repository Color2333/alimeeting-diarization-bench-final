# Script Directory Guide

This directory keeps legacy command paths stable for reproducibility. Many
reports and regression runners refer to scripts as `scripts/<name>.py`, so the
files intentionally remain in this top-level directory instead of being moved
into nested folders.

Use the sections below as the supported navigation layer.

## Stable Submission Entrypoints

These are the scripts reviewers should start with.

| Script | Purpose |
|---|---|
| `quick_start.py` | Shortest offline reproduction path; regenerates the all-cached default result and prints key metrics. |
| `run_realtime_diarization_system.py` | Default offline diarization enhancement system. |
| `run_realtime_batch.py` | Batch wrapper around the default offline system. |
| `run_realtime_system_regression.py` | Full offline regression and self-check refresh. |
| `check_realtime_system_outputs.py` | Self-check for final metrics, audits, gates, and promotion boundaries. |
| `check_timeline_integrity.py` | Timeline structural integrity check. |

## Final-System Artifact Builders

These scripts rebuild the derived artifacts used by the default submission
path.

| Group | Scripts |
|---|---|
| Feature/materialization | `build_audio_window_features.py`, `materialize_llm_guard_tuning.py`, `materialize_tuned_writeback_gate.py` |
| Selector and overlay search | `validate_guarded_slow_selector.py`, `search_system_selector_policies.py`, `search_rare_selector_overlay_policies.py`, `search_slow_sanitization_policies.py`, `search_speaker_track_sanitization_policies.py`, `search_audio_guided_sanitization_policies.py`, `search_audio_boundary_adjustment_policies.py`, `search_recording_balanced_overlays.py` |
| Runtime output evaluation | `evaluate_rule_writeback_timeline.py`, `audit_realtime_batch_consistency.py`, `audit_clipped_baselines.py`, `audit_baseline_leaderboard.py`, `audit_runtime_overlay_contributions.py`, `audit_recording_level_stability.py` |
| Candidate-surface governance | `audit_external_candidate_source_inventory.py`, `search_external_candidate_surfaces.py`, `build_external_candidate_reproduction_plan.py`, `audit_baseline_headroom.py` |
| Promotion and readiness | `build_system_promotion_gate.py`, `diagnose_true_heldout_readiness.py`, `diagnose_selector_robustness.py`, `diagnose_recording_stability_blockers.py`, `build_research_next_experiment_queue.py` |

## Research and Diagnostic Scripts

These are retained for traceability of the development process. They are not
required for the quick-start path.

| Prefix | Meaning |
|---|---|
| `analyze_*` | One-off analyses of model behavior, latency, LLM safety, and candidate windows. |
| `audit_*` | Evidence checks and fairness/coverage audits. |
| `build_live_*`, `build_post_live_*`, `run_live_*`, `run_post_live_*` | Live-run planning, receipts, post-live scoring plans, and promotion-gate support. These do not run live calls unless explicitly invoked with live flags. |
| `llm_*`, `omni_*`, `policy_*`, `runtime_safe_*` | LLM/Omni experiment support and policy-decision surfaces. |
| `summarize_*`, `compare_*`, `simulate_*` | Report summaries, run comparisons, and latency/scheduling simulations. |
| `setup_*`, `run_*_smoke.sh`, `run_pyannote*.sh`, `run_sortformer*.sh`, `run_diarizen*.sh` | Local model/environment setup and smoke tests. |

## Maintenance Rules

- Keep `quick_start.py`, `run_realtime_diarization_system.py`,
  `run_realtime_batch.py`, and `run_realtime_system_regression.py` stable.
- Do not move scripts into nested folders unless every `scripts/<name>` command
  in README, reports, regression runners, and generated artifacts is updated.
- Presentation-generation scripts are intentionally excluded from the final
  package. The finished deck is kept at
  `outputs/final_effect_presentation.pptx`.
- Live/API scripts must stay opt-in. The default submission path is offline and
  must keep DeepSeek/Qwen/Omni live call counts at zero.
