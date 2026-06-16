# Alt SOTA Baselines and LLM Post-processing Smoke Test

> Date: 2026-06-03  
> Scope: DiariZen / Sortformer baseline integration and LLM diarization post-processing scaffold

## Implemented

- Added uv environment scripts:
  - `scripts/model_runs/setup_diarizen_uv.sh`
  - `scripts/model_runs/run_diarizen_uv_smoke.sh`
  - `scripts/model_runs/setup_sortformer_uv.sh`
  - `scripts/model_runs/run_sortformer_uv_smoke.sh`
- Added `sortformer` model entry for NVIDIA NeMo Sortformer:
  - model registry key: `sortformer`
  - wrapper: `alimeeting_diarization_bench/models/sortformer.py`
  - expected checkpoint: `nvidia/diar_sortformer_4spk-v1`
- Kept and tested `diarizen` model entry:
  - model registry key: `diarizen`
  - expected checkpoint: `BUT-FIT/diarizen-wavlm-large-s80-md-v2`
- Added per-segment detail fields to benchmark summaries:
  - `pred_segments`
  - `gt_segments`
  - `pred_text`
  - `gt_text`
- Added LLM post-processing utility:
  - `scripts/llm/llm_diarization_postprocess.py`
  - supports prompt export and OpenAI-compatible relabeling mode

## DiariZen Trial

### Current shared environment trial

What worked:

- Cloned official DiariZen source to `/private/tmp/diarizen_src`.
- Installed DiariZen source with `pip install -e /private/tmp/diarizen_src --no-deps`.
- `from diarizen.pipelines.inference import DiariZenPipeline` imports successfully.
- HuggingFace model files for `BUT-FIT/diarizen-wavlm-large-s80-md-v2` downloaded successfully.

What failed:

```text
SpeakerDiarization.__init__() got an unexpected keyword argument 'config'
```

Cause:

- Current environment uses a newer `pyannote.audio` whose `SpeakerDiarization` constructor no longer accepts DiariZen's custom `config`, `seg_duration`, and `device` arguments.
- DiariZen official installation expects its bundled `pyannote-audio` fork/submodule, not the current PyAnnote Community-1 environment.

Conclusion:

- DiariZen is a valid high-priority baseline, but should be run in an isolated environment. Do not overwrite the current working PyAnnote environment.

### uv isolated environment trial

Environment:

- Python: 3.10.20 downloaded by `uv` into `.uv-python`.
- venv: `.venv_diarizen`.
- DiariZen source: `/private/tmp/diarizen_src`.
- Core pins after fixing version drift:
  - `torch==2.1.1`
  - `torchaudio==2.1.1`
  - `numpy==1.26.4`
  - DiariZen bundled `pyannote-audio` fork

Commands:

```bash
bash scripts/model_runs/setup_diarizen_uv.sh
SAMPLES=8 OUTPUT_DIR=outputs/diarizen_uv_8 bash scripts/model_runs/run_diarizen_uv_smoke.sh
```

Result on 8 stratified 30s segments:

| Model | Count mode | DER | Miss | FA | Conf | Spk match | Latency |
|---|---|---:|---:|---:|---:|---:|---:|
| DiariZen Large v2 | none | 18.09% | 5.34% | 4.08% | 8.67% | 50.0% | 21.5s |

Result files:

- `outputs/diarizen_uv_8/diarizen-large-v2/default__spk_none/summary.json`
- `outputs/diarizen_uv_8/diarizen-large-v2/default__spk_none/results.csv`
- `outputs/diarizen_uv_24/diarizen-large-v2/default__spk_none/summary.json`
- `outputs/diarizen_uv_24/diarizen-large-v2/default__spk_none/results.csv`

Comparison against earlier 8-segment PyAnnote results:

| Model | Count mode | DER | Conf | Spk match |
|---|---|---:|---:|---:|
| PyAnnote Community-1 | none | 32.26% | 15.05% | 25.0% |
| PyAnnote Community-1 | oracle | 26.92% | 9.71% | 100.0% |
| DiariZen Large v2 | none | 18.09% | 8.67% | 50.0% |

Interpretation:

- DiariZen is now the strongest local/open baseline observed in this project.
- It beats PyAnnote Community-1 even without oracle speaker count on this 8-segment sample.
- It is much slower on Mac CPU. A full 482-segment run should be moved to GPU/Linux or a remote GPU host.

### 24-segment validation

Result on 24 stratified 30s segments:

| Model | Count mode | DER | Miss | FA | Conf | Spk match | Latency |
|---|---|---:|---:|---:|---:|---:|---:|
| DiariZen Large v2 | none | 11.76% | 3.70% | 4.05% | 4.01% | 75.0% | 22.6s |

Same-scale comparison against current local baselines:

| Model | Count mode | DER | Miss | FA | Conf | Spk match | Latency |
|---|---|---:|---:|---:|---:|---:|---:|
| DiariZen Large v2 | none | 11.76% | 3.70% | 4.05% | 4.01% | 75.0% | 22.6s |
| Sortformer 4spk v1 | none | 23.45% | 18.07% | 2.44% | 2.95% | 45.8% | 0.5s |
| PyAnnote Community-1 | none | 23.96% | 8.98% | 4.14% | 10.84% | 33.3% | 1.9s |
| PyAnnote Community-1 | oracle | 33.12% | 8.98% | 4.14% | 20.00% | 100.0% | 1.8s |

Interpretation:

- DiariZen remains the best accuracy baseline after expanding from 8 to 24 segments.
- Its main gain is not just lower Miss; it cuts speaker confusion sharply compared with PyAnnote no-count and oracle runs.
- Sortformer has similar DER to PyAnnote no-count on this 24-segment set, but the error profile is different: Sortformer mostly misses speech, while PyAnnote has higher speaker confusion.
- The progress deck was updated to show this table and chart on the "DER 性能对比与误差分解" slide.

### 48-segment larger run

Command:

```bash
MPLCONFIGDIR=/private/tmp/matplotlib .venv_diarizen/bin/python -m alimeeting_diarization_bench.run \
  --model diarizen \
  --window-size 30 \
  --sampling-mode stratified \
  --total-samples 48 \
  --seed 42 \
  --collar 0.0 \
  --speaker-count-mode none \
  --output-dir outputs/diarizen_uv_48
```

Raw result:

| Model | Samples | DER | Miss | FA | Conf | Spk match | Latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| DiariZen Large v2 | 48 | 21.04% | 4.92% | 10.66% | 5.45% | 66.7% | 25.6s |

Outlier check:

| View | DER |
|---|---:|
| Raw mean | 21.04% |
| Median | 11.14% |
| Mean excluding the single DER > 100% segment | 13.84% |
| Drop min/max mean | 14.08% |

Top outlier:

| Recording | Segment | DER | Miss | FA | Conf | Pred / GT speakers |
|---|---:|---:|---:|---:|---:|---:|
| R8003_M8001 | 5 | 359.49% | 0.60% | 334.84% | 24.04% | 2 / 2 |

Interpretation:

- The 48-segment raw mean is strongly inflated by one extreme false-alarm segment.
- The median and outlier-filtered mean remain close to the 24-segment result, so DiariZen is still the strongest accuracy baseline.
- The larger run reveals a new engineering issue: the final system should include post-filtering / VAD sanity checks for abnormal over-segmentation windows.
- The difficult normal windows are mostly in 3-4 speaker meetings, where confusion still dominates; this supports the visual registration + voiceprint memory direction.

## Sortformer Trial

What worked:

- Added Sortformer wrapper and CLI registry.
- Verified parser behavior for NeMo diarize output formats.
- `python -m alimeeting_diarization_bench.run --help` now includes `sortformer`.
- Built `.venv_sortformer` with `uv`.
- Installed `nemo_toolkit[asr]`.
- Verified `SortformerEncLabelModel` imports successfully.
- Ran 1, 8, and 24 segment smoke/validation experiments.

Commands:

```bash
bash scripts/model_runs/setup_sortformer_uv.sh
SAMPLES=8 WINDOW_SIZE=90 OUTPUT_DIR=outputs/sortformer_uv_8_90s \
  bash scripts/model_runs/run_sortformer_uv_smoke.sh
```

Results:

| Model | Window | Samples | DER | Miss | FA | Conf | Spk match | Latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sortformer 4spk v1 | 30s | 1 | 10.72% | 7.58% | 2.93% | 0.21% | 100.0% | 0.9s |
| Sortformer 4spk v1 | 30s | 8 | 33.25% | 23.95% | 3.68% | 5.62% | 50.0% | 0.4s |
| Sortformer 4spk v1 | 30s | 24 | 23.45% | 18.07% | 2.44% | 2.95% | 45.8% | 0.5s |
| Sortformer 4spk v1 | 90s | 8 | 24.29% | 18.91% | 3.68% | 1.71% | 62.5% | 1.3s |

Result files:

- `outputs/sortformer_uv_smoke/nemo-sortformer-4spk-v1/default__spk_none/summary.json`
- `outputs/sortformer_uv_8/nemo-sortformer-4spk-v1/default__spk_none/summary.json`
- `outputs/sortformer_uv_24/nemo-sortformer-4spk-v1/default__spk_none/summary.json`
- `outputs/sortformer_uv_8_90s/nemo-sortformer-4spk-v1/default__spk_none/summary.json`

Conclusion:

- Sortformer is usable locally through an isolated uv environment.
- It is much faster than DiariZen on Mac CPU: about 0.4-1.3s per segment versus DiariZen's about 21.5s per 30s segment.
- Its current weakness is high miss rate. On 30s windows, the 8-segment DER is 33.25%, mostly from 23.95% miss.
- The 90s window is more compatible with the checkpoint's configured 90s session length and improves DER to 24.29%, but this is still behind DiariZen's 18.09% on the 8-segment 30s sample.
- Practical role: fast low-latency baseline / online candidate, not the current best offline DER baseline.

## LLM Post-processing Trial

Smoke run:

```bash
python -m alimeeting_diarization_bench.run \
  --model pyannote_community \
  --window-size 30 \
  --sampling-mode stratified \
  --total-samples 2 \
  --seed 42 \
  --collar 0.0 \
  --speaker-count-mode none \
  --output-dir outputs/llm_postprocess_smoke
```

Result:

| Model | Segments | DER | Miss | FA | Conf | Spk match |
|---|---:|---:|---:|---:|---:|---:|
| PyAnnote Community-1 no-count | 2 | 17.34% | 8.12% | 4.49% | 4.73% | 50.0% |

Prompt export:

```bash
python scripts/llm/llm_diarization_postprocess.py \
  outputs/llm_postprocess_smoke/pyannote-community-1/default__spk_none/summary.json \
  --mode export
```

Output:

- `outputs/llm_postprocess_smoke/pyannote-community-1/default__spk_none/prompts.jsonl`

Limitation:

- PyAnnote outputs no transcript text, so exported prompts have `has_transcript_text=false`.
- This validates the engineering interface, but not semantic correction quality.
- To evaluate LLM semantic post-processing properly, use FunASR/Paraformer/GPT output or add an ASR step before LLM relabeling.
- Current environment has no `GPT_API_KEY`, `OSS_ACCESS_KEY_ID`, or `OSS_ACCESS_KEY_SECRET`, so online LLM relabeling and DashScope ASR diarization were not run.

## Recommended Next Step

1. Run DiariZen on a larger sample:
   - 48 segments locally to check variance and outliers.
   - 120 or 482 segments on GPU/Linux for the final reported number.
2. Use Sortformer for speed-focused experiments:
   - Keep `WINDOW_SIZE=90` as the default.
   - Diagnose high miss rate before using it as the main accuracy baseline.
3. Run LLM post-processing only on outputs with text:
   - FunASR/Paraformer native diarization output
   - or PyAnnote/DiariZen segments aligned with an ASR transcript

## Sources

- DiariZen official repository: https://github.com/BUTSpeechFIT/DiariZen
- DiariZen benchmark/model notes: https://github.com/BUTSpeechFIT/DiariZen#benchmark
- NVIDIA Sortformer model card: https://huggingface.co/nvidia/diar_sortformer_4spk-v1
- NVIDIA NeMo Sortformer docs: https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/asr/speaker_diarization/results.html
