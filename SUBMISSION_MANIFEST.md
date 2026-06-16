# Submission Manifest

This folder is the curated final submission package for the current
AliMeeting diarization development-pool result.

## Contents

- `README.md`: end-to-end reproducibility guide, metrics, artifacts, and
  promotion boundaries.
- `pyproject.toml`, `requirements.txt`, `.env.example`: install and environment
  setup.
- `alimeeting_diarization_bench/`: benchmark package and model/evaluation code.
- `scripts/`: reproducibility, batch, regression, self-check, audit, and search
  scripts. `scripts/quick_start.py` is the shortest offline reproduction
  entrypoint, and `scripts/README.md` is the script navigation guide.
  Presentation-generation scripts are intentionally excluded from the final code
  package; only the finished deck is retained.
- `docs/`: report-generation support files retained from the source workspace.
- `outputs/`: curated result and cache subset needed for the documented
  offline reproduction paths.
- `outputs/final_effect_presentation.pptx`: final presentation deck for the
  submitted result.

## Included Output Groups

- Cached base model summaries:
  - `outputs/sortformer_uv_120/`
  - `outputs/diarizen_uv_120/`
  - `outputs/diarizen_uv_48/`
- Default-system source artifacts:
  - `outputs/writeback_gate_120/`
  - `outputs/segment_patches/`
  - `outputs/runtime_safe_llm_window_batch/`
  - `outputs/rule_writeback_timeline_120/`
  - `outputs/audio_window_features/`
  - `outputs/system_selector_validation/`
  - `outputs/system_selector_search/`
  - `outputs/slow_sanitization_search/`
  - `outputs/rare_selector_search/`
- Final outputs and verification reports:
  - `outputs/system_demo/`
  - `outputs/realtime_batch/`
  - `outputs/system_regression/`
  - `outputs/system_self_check/`
  - `outputs/timeline_integrity/`
  - `outputs/clipped_baseline_audit/`
  - `outputs/baseline_leaderboard_audit/`
  - `outputs/runtime_overlay_contributions/`
  - `outputs/recording_level_stability/`
  - `outputs/system_promotion_gate/`
  - `outputs/true_heldout_readiness/`
  - `outputs/selector_robustness_diagnosis/`
  - `outputs/recording_stability_blockers/`
  - `outputs/research_progress_snapshot/`
- Candidate-surface diagnostics:
  - `outputs/audio_guided_sanitization_search/`
  - `outputs/audio_boundary_adjustment_search/`
  - `outputs/speaker_track_sanitization_search/`
  - `outputs/recording_balanced_overlay_search/`
  - `outputs/recording_context_overlay_search/`
  - `outputs/external_candidate_source_inventory/`
  - `outputs/external_candidate_surface_search/`
  - `outputs/external_candidate_reproduction_plan/`
  - `outputs/baseline_headroom_audit/`
- Presentation:
  - `outputs/final_effect_presentation.pptx`

## Excluded From Package

The final package intentionally excludes local virtual environments, local
package caches, Python bytecode caches, and exploratory outputs that are not
part of the documented reproduction chain.

## Expected Verification

From this folder:

```bash
python -m py_compile \
  alimeeting_diarization_bench/run.py \
  alimeeting_diarization_bench/evaluation/runner.py \
  scripts/run_realtime_diarization_system.py \
  scripts/run_realtime_batch.py \
  scripts/quick_start.py \
  scripts/run_realtime_system_regression.py \
  scripts/check_realtime_system_outputs.py \
  scripts/search_external_candidate_surfaces.py

python -m alimeeting_diarization_bench.run --help
```

The included latest regression artifacts should report:

```text
outputs/system_regression/realtime_system_regression.json
  status = pass
  passed_steps = 29
  total_steps = 29
  metrics_summary.final_der = 0.16492333333333334
  metrics_summary.beats_all_baselines = true

outputs/system_demo/all_cached_recordings/metrics.json
  metrics.processed_audio_sec = 3600.0
  metrics.offline_replay_rtf = 0.0008552033371395535

outputs/system_self_check/realtime_system_self_check.json
  status = warn
  pass_count = 40
  warn_count = 4
  fail_count = 0
```
