# AliMeeting SOTA Exploration Notes

> Date: 2026-06-03  
> Scope: local/open diarization candidates, speaker-count hint ablation, and PyAnnote parameter tuning  
> Dataset sample: AliMeeting Eval, 8 and 24 stratified 30s segments, collar=0.0s

## What Changed

- Added `--speaker-count-mode` to the benchmark CLI:
  - `oracle`: pass GT speaker count to the model. This approximates the proposed one-time visual enrollment/count signal.
  - `none`: pass no speaker count. This is pure audio-only zero-shot counting.
  - `bounds`: pass `min_speakers`/`max_speakers` when supported by the model.
- Added `pyannote_community` model entry for `pyannote/speaker-diarization-community-1`.
- Added `diarizen` model entry for `BUT-FIT/diarizen-wavlm-large-s80-md-v2`.
- Split result output directories by model and speaker-count mode to avoid overwriting comparisons.
- Added helper scripts:
  - `scripts/model_runs/run_speaker_count_ablation.sh`
  - `scripts/model_runs/run_local_sota_models.sh`
  - `scripts/model_runs/run_pyannote_param_grid.sh`
  - `scripts/model_runs/run_pyannote_fafb_grid.sh`
  - `scripts/analysis/summarize_param_tuning.py`

## Initial Results

| Model | Count mode | DER | Miss | FA | Conf | Spk match | Latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| PyAnnote 3.1 | oracle | 26.33% | 12.72% | 4.49% | 9.12% | 100.0% | 1.73s |
| PyAnnote Community-1 | oracle | 26.92% | 12.72% | 4.49% | 9.71% | 100.0% | 1.90s |
| PyAnnote Community-1 | none | 32.26% | 12.72% | 4.49% | 15.05% | 25.0% | 1.80s |
| PyAnnote Community-1 | bounds 1-8 | 32.26% | 12.72% | 4.49% | 15.05% | 25.0% | 1.81s |

Result files:

- `outputs/sota_exploration/pyannote-3.1/default__spk_oracle/summary.json`
- `outputs/sota_exploration/pyannote-community-1/default__spk_oracle/summary.json`
- `outputs/sota_exploration/pyannote-community-1/default__spk_none/summary.json`
- `outputs/sota_exploration/pyannote-community-1/default__spk_bounds__1-8/summary.json`

## Takeaways

1. Exact speaker count can be valuable, but the effect is sample-dependent. On the initial 8-segment sample, Community-1 improves from 32.26% DER to 26.92% DER when given the exact count.
2. The 8-segment gain comes almost entirely from lower speaker confusion: 15.05% to 9.71%. Miss and FA stay unchanged.
3. Wide bounds are not enough. `min=1, max=8` behaves the same as no speaker-count hint.
4. Community-1 did not beat PyAnnote 3.1 on this small sample, but this is not conclusive. The official benchmark advantage should be checked on the full 482-segment set.
5. DiariZen is wired into the benchmark, but the local `diarizen` package is not installed yet.

## Parameter Tuning

PyAnnote Community-1 exposes these instantiated parameters locally:

```text
segmentation.min_duration_off = 0.0
clustering.threshold = 0.6
clustering.Fa = 0.07
clustering.Fb = 0.8
```

Threshold-only grid did not move the metric on the 8-segment sample. Both `oracle` and `none` modes were identical for thresholds `0.45, 0.50, 0.55, 0.60, 0.65, 0.70`.

### 8-segment Fa/Fb grid, oracle count

| Params | DER | Miss | FA | Conf | Spk match |
|---|---:|---:|---:|---:|---:|
| `Fa=0.03,Fb=0.8` | 26.71% | 12.72% | 4.49% | 9.50% | 100.0% |
| `Fa=0.07,Fb=0.6` | 26.92% | 12.72% | 4.49% | 9.71% | 100.0% |
| `Fa=0.07,Fb=0.8` | 26.92% | 12.72% | 4.49% | 9.71% | 100.0% |
| `Fa=0.07,Fb=1.0` | 26.92% | 12.72% | 4.49% | 9.71% | 100.0% |
| `Fa=0.12,Fb=0.8` | 26.93% | 12.72% | 4.49% | 9.72% | 100.0% |

Best small-sample setting was `Fa=0.03,Fb=0.8`, but the improvement was only 0.21pp absolute DER.

### 24-segment validation

This uses the same seed and stratified allocation: 8 two-speaker, 8 three-speaker, and 8 four-speaker 30s segments.

| Mode | Params | DER | Miss | FA | Conf | Spk match |
|---|---|---:|---:|---:|---:|---:|
| oracle | default | 33.12% | 8.98% | 4.14% | 20.00% | 100.0% |
| oracle | `Fa=0.03,Fb=0.8` | 32.98% | 8.98% | 4.14% | 19.86% | 100.0% |
| none | default | 23.96% | 8.98% | 4.14% | 10.84% | 33.3% |
| none | `Fa=0.03,Fb=0.8` | 35.44% | 8.98% | 4.14% | 22.31% | 25.0% |

The 24-segment validation changes the interpretation:

1. `Fa=0.03,Fb=0.8` is not a robust tuning win. It barely helps when exact count is forced, and it hurts badly in no-count mode.
2. Passing exact `num_speakers` is not always DER-optimal for short windows. In this 24-segment sample, no-count mode has lower DER but poor predicted speaker-count match.
3. Visual information should probably not be used as a hard `num_speakers` knob alone. It is more promising as:
   - recording/session-level participant inventory,
   - active-speaker enrollment anchors,
   - voiceprint-based identity reassignment after diarization,
   - soft count consistency over longer time windows.

Result files:

- `outputs/param_tuning_fafb_oracle/pyannote-community-1/default__spk_oracle__params_44a8a388/summary.json`
- `outputs/param_tuning_validate_24/pyannote-community-1/default__spk_oracle/summary.json`
- `outputs/param_tuning_validate_24/pyannote-community-1/default__spk_oracle__params_44a8a388/summary.json`
- `outputs/speaker_count_validate_24/pyannote-community-1/default__spk_none/summary.json`
- `outputs/speaker_count_validate_24/pyannote-community-1/default__spk_none__params_44a8a388/summary.json`

## Commands

```bash
python -m alimeeting_diarization_bench.run \
  --model pyannote_community \
  --window-size 30 \
  --sampling-mode stratified \
  --total-samples 8 \
  --seed 42 \
  --collar 0.0 \
  --speaker-count-mode oracle \
  --output-dir outputs/sota_exploration
```

```bash
python -m alimeeting_diarization_bench.run \
  --model pyannote_community \
  --window-size 30 \
  --sampling-mode stratified \
  --total-samples 8 \
  --seed 42 \
  --collar 0.0 \
  --speaker-count-mode none \
  --output-dir outputs/sota_exploration
```

```bash
python -m alimeeting_diarization_bench.run \
  --model pyannote_community \
  --window-size 30 \
  --sampling-mode stratified \
  --total-samples 8 \
  --seed 42 \
  --collar 0.0 \
  --speaker-count-mode bounds \
  --min-speakers 1 \
  --max-speakers 8 \
  --output-dir outputs/sota_exploration
```

## Next Experiments

1. Full 482-segment rerun:
   - PyAnnote 3.1 oracle
   - PyAnnote Community-1 oracle
   - PyAnnote Community-1 none
2. Visual-informed voiceprint path:
   - Use one-time visual enrollment or active-speaker detections to build speaker anchors.
   - Keep audio diarization no-count/default as the base segmentation when it gives lower DER.
   - Reassign speaker labels with embedding similarity to anchors, then enforce session-level identity consistency.
3. DiariZen setup:
   - Install DiariZen in an isolated environment.
   - Run `diarizen-large-v2` on the same 8-segment sample, then full 482 segments if stable.
4. Stop broad PyAnnote hyperparameter sweeping unless the full-run error analysis shows a specific failure mode. Current evidence says threshold and Fa/Fb are weak levers.
