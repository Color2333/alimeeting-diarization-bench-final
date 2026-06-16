# External Candidate Reproduction Plan

- Runtime contract: `external_candidate_reproduction_plan_no_inference`
- Status: `ready_for_default_runtime_promotion_check`
- Source: `diarizen-large-v2/diarizen-large-v2/spk_none::outputs/diarizen_uv_48/diarizen-large-v2/default__spk_none`
- Source coverage: `120/120`
- Missing windows: `0`
- Stale checkpoint windows: `0`
- Best external-search delta: `0.00016666666666498298` pp
- Resume supported: `True`
- Estimated remaining latency: `0.0` sec

## Manifest Resume Command

```bash
.venv_diarizen/bin/python -m alimeeting_diarization_bench.run --model diarizen --window-size 30 --sampling-mode stratified --total-samples 120 --seed 42 --speaker-count-mode none --output-dir outputs/diarizen_uv_48 --segments-manifest outputs/external_candidate_reproduction_plan/missing_external_candidate_windows.csv --summary-name missing_external_candidate_windows_summary.json --results-name missing_external_candidate_windows_results.csv
```

## Full Summary Refresh Command

```bash
.venv_diarizen/bin/python -m alimeeting_diarization_bench.run --model diarizen --window-size 30 --sampling-mode stratified --total-samples 120 --seed 42 --speaker-count-mode none --output-dir outputs/diarizen_uv_48
```

## Gates Before Default Runtime

- `pass` source_full_current_pool_coverage: 120/120 windows covered
- `pass` best_policy_windows_available: 2/2 selected windows available
- `blocked` meaningful_development_delta: 0.00016666666666498298pp vs minimum 0.05pp
- `pass` zero_overlay_losses: 0
- `pass` zero_negative_recordings: 0

## Reading

- This artifact does not run DiariZen or change default runtime metrics.
- The explicit manifest command processes only missing windows and writes a separate missing-window summary.
- The full summary refresh command reruns the 120-window selection and should mostly skip completed checkpoint entries, then writes `summary.json`.
