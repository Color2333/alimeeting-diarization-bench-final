# Download And Dependency Manifest

This file summarizes the external resources needed to reproduce or extend the
final AliMeeting diarization submission.

## Default Offline Reproduction

The default submitted path does not need live API keys or model downloads. It
uses cached Sortformer and DiariZen outputs already included under `outputs/`.

Run:

```bash
python -m pip install -e .
alimeeting-quick-start
```

Expected result:

```text
final DER: 16.4923%
live API calls: DeepSeek=0, Qwen=0, Omni=0
```

## Dataset

Dataset:

- AliMeeting
- Submitted split: AliMeeting Eval set
- Evaluation pool: 8 Eval recordings, 120 windows
- Window size: 30 seconds

Expected local layout for non-cached reruns:

```text
~/data/AliMeeting/Eval_Ali/Eval_Ali_far/audio_dir/
~/data/AliMeeting/AliMeeting_manifests/
```

Environment overrides:

```bash
export ALIMEETING_AUDIO_DIR=~/data/AliMeeting/Eval_Ali/Eval_Ali_far/audio_dir
export ALIMEETING_MANIFEST_DIR=~/data/AliMeeting/AliMeeting_manifests
```

## Core Cached Model Artifacts

Fast baseline:

```text
outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json
```

Slow baseline:

```text
outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json
```

The final system replays these cached outputs and applies offline enhancement
artifacts from `outputs/`.

## Optional Live / Non-Cached Model Resources

Only needed if rerunning model inference instead of using cached outputs.

| Model path | External resource |
|---|---|
| Sortformer | NVIDIA NeMo / `nvidia/diar_sortformer_4spk-v1` |
| DiariZen | `BUT-FIT/diarizen-wavlm-large-s80-md-v2` |
| PyAnnote | `pyannote/speaker-diarization-3.1` or community model |
| Qwen / DashScope adapters | DashScope API key |
| GPT audio adapter | OpenAI-compatible GPT audio API key |

Credentials are documented in `.env.example`. The final offline reproduction
path does not require them.

## Python Package

Install from the repository root:

```bash
python -m pip install -e .
```

Key package entrypoints:

```text
alimeeting-quick-start
alimeeting-realtime
alimeeting-batch
alimeeting-regression
alimeeting-self-check
alimeeting-timeline-check
```
