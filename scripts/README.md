# Script Directory Guide

This directory is intentionally structured by role. The final submission
entrypoints are isolated under `scripts/entrypoints/`; supporting scripts are
grouped so the reproducibility path is easy to inspect without mixing it with
research-only utilities.

All Python scripts in these subdirectories include a local import bootstrap, so
they can still be executed directly by file path from the repository root.
After `python -m pip install -e .`, the stable entrypoints are also available
as package commands.

## Stable Submission Entrypoints

These are the scripts reviewers should start with.

| File path | Installed command | Purpose |
|---|---|---|
| `scripts/entrypoints/quick_start.py` | `alimeeting-quick-start` | Shortest offline reproduction path; regenerates the all-cached default result and prints key metrics. |
| `scripts/entrypoints/run_realtime_diarization_system.py` | `alimeeting-realtime` | Default offline diarization enhancement system. |
| `scripts/entrypoints/run_realtime_batch.py` | `alimeeting-batch` | Batch wrapper around the default offline system. |
| `scripts/entrypoints/run_realtime_system_regression.py` | `alimeeting-regression` | Full offline regression and self-check refresh. |
| `scripts/entrypoints/check_realtime_system_outputs.py` | `alimeeting-self-check` | Self-check for final metrics, audits, gates, and promotion boundaries. |
| `scripts/entrypoints/check_timeline_integrity.py` | `alimeeting-timeline-check` | Timeline structural integrity check. |

The dispatcher command is also available:

```bash
alimeeting-final quick-start
alimeeting-final realtime --all-cached-recordings --output-dir outputs/system_demo/all_cached_recordings
alimeeting-final regression
```

## Directory Layout

```text
scripts/
  entrypoints/   # reviewer-facing quick start, realtime, batch, regression, checks
  builders/      # deterministic artifact builders for features, gates, manifests, reports
  search/        # selector, overlay, readiness, and policy search/diagnosis scripts
  audits/        # fairness, consistency, baseline, source, and stability audits
  analysis/      # analysis and summarization scripts retained for traceability
  llm/           # offline/live LLM policy, guard, Omni, and writeback support scripts
  live/          # opt-in live-run planning, receipts, launchers, and post-live scoring
  model_runs/    # local model setup and batch shell wrappers
  misc/          # legacy utilities that are not part of the default reproduction chain
```

## Final-System Artifact Builders

These scripts rebuild the derived artifacts used by the default submission
path.

| Group | Scripts |
|---|---|
| Feature/materialization | `scripts/builders/build_audio_window_features.py`, `scripts/llm/materialize_llm_guard_tuning.py`, `scripts/llm/materialize_tuned_writeback_gate.py` |
| Selector and overlay search | `scripts/search/validate_guarded_slow_selector.py`, `scripts/search/search_system_selector_policies.py`, `scripts/search/search_rare_selector_overlay_policies.py`, `scripts/search/search_slow_sanitization_policies.py`, `scripts/search/search_speaker_track_sanitization_policies.py`, `scripts/search/search_audio_guided_sanitization_policies.py`, `scripts/search/search_audio_boundary_adjustment_policies.py`, `scripts/search/search_recording_balanced_overlays.py` |
| Runtime output evaluation | `scripts/analysis/evaluate_rule_writeback_timeline.py`, `scripts/audits/audit_realtime_batch_consistency.py`, `scripts/audits/audit_clipped_baselines.py`, `scripts/audits/audit_baseline_leaderboard.py`, `scripts/audits/audit_runtime_overlay_contributions.py`, `scripts/audits/audit_recording_level_stability.py` |
| Candidate-surface governance | `scripts/audits/audit_external_candidate_source_inventory.py`, `scripts/search/search_external_candidate_surfaces.py`, `scripts/builders/build_external_candidate_reproduction_plan.py`, `scripts/audits/audit_baseline_headroom.py` |
| Promotion and readiness | `scripts/builders/build_system_promotion_gate.py`, `scripts/search/diagnose_true_heldout_readiness.py`, `scripts/search/diagnose_selector_robustness.py`, `scripts/search/diagnose_recording_stability_blockers.py`, `scripts/builders/build_research_next_experiment_queue.py` |

## Maintenance Rules

- Keep `scripts/entrypoints/` stable; these paths are the documented review
  surface.
- Prefer adding new deterministic builders to `scripts/builders/`, audits to
  `scripts/audits/`, and policy/search work to `scripts/search/`.
- Keep live/API work opt-in under `scripts/live/` or `scripts/llm/`. The default
  submission path must remain offline and keep DeepSeek/Qwen/Omni live call
  counts at zero.
- Presentation-generation scripts are excluded from the final code package. The
  finished deck is retained at `outputs/final_effect_presentation.pptx`.
