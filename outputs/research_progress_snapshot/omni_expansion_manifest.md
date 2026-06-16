# Omni Expansion Manifest

- Runtime contract: `omni_expansion_manifest_ready_no_live_calls_no_timeline_writeback`
- Selected windows: `48` / target `48`
- Anchor smoke windows: `12`
- New runtime-proxy windows: `36`
- Planned model calls: `96`
- Audio missing: `0`
- Live call status: `not_run_manifest_only`
- No timeline writeback: `True`

## Run Command

```bash
python scripts/omni_guard_window_batch.py --input-windows-csv outputs/research_progress_snapshot/omni_expansion_manifest.csv --model qwen3.5-omni-flash --model qwen3.5-omni-plus-2026-03-15 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/omni_guard/omni_expansion_48_live.jsonl
```

## Selected Windows

| Window | Role | Prior bucket | Proxy score | Proxy reasons | Audio |
|---|---|---|---:|---|---|
| `R8001_M8004:30:1` | `anchor_smoke_window` | `high` | 0.0 |  | `1` |
| `R8001_M8004:30:3` | `anchor_smoke_window` | `high` | 0.0 |  | `1` |
| `R8001_M8004:30:5` | `anchor_smoke_window` | `medium` | 0.0 |  | `1` |
| `R8003_M8001:30:3` | `anchor_smoke_window` | `clean` | 0.0 |  | `1` |
| `R8003_M8001:30:4` | `anchor_smoke_window` | `medium` | 0.0 |  | `1` |
| `R8003_M8001:30:5` | `anchor_smoke_window` | `high` | 0.0 |  | `1` |
| `R8007_M8010:30:4` | `anchor_smoke_window` | `high` | 0.0 |  | `1` |
| `R8007_M8011:30:0` | `anchor_smoke_window` | `clean` | 0.0 |  | `1` |
| `R8008_M8013:30:2` | `anchor_smoke_window` | `medium` | 0.0 |  | `1` |
| `R8009_M8018:30:0` | `anchor_smoke_window` | `medium` | 0.0 |  | `1` |
| `R8009_M8019:30:0` | `anchor_smoke_window` | `clean` | 0.0 |  | `1` |
| `R8009_M8020:30:4` | `anchor_smoke_window` | `clean` | 0.0 |  | `1` |
| `R8001_M8004:30:12` | `new_runtime_proxy_window` | `runtime_proxy` | 20.632 | cross_model_disagreement_high;cross_model_segment_count_gap;cross_model_speaker_count_mismatch;pred_speech_too_long;slow_speech_much_longer_than_fast | `1` |
| `R8001_M8004:30:9` | `new_runtime_proxy_window` | `runtime_proxy` | 20.341 | cross_model_disagreement_high;cross_model_segment_count_gap;cross_model_speaker_count_mismatch;pred_speech_too_long;slow_speech_much_longer_than_fast | `1` |
| `R8001_M8004:30:4` | `new_runtime_proxy_window` | `runtime_proxy` | 20.010 | cross_model_disagreement_high;cross_model_segment_count_gap;cross_model_speaker_count_mismatch;pred_speech_too_long;slow_speech_much_longer_than_fast | `1` |
| `R8008_M8013:30:7` | `new_runtime_proxy_window` | `runtime_proxy` | 19.257 | cross_model_disagreement_high;cross_model_segment_count_gap;cross_model_speaker_count_mismatch;pred_speech_too_long;slow_speech_much_longer_than_fast | `1` |
| `R8007_M8011:30:9` | `new_runtime_proxy_window` | `runtime_proxy` | 17.546 | cross_model_disagreement_high;cross_model_segment_count_gap;cross_model_speaker_count_mismatch;pred_speech_too_long;slow_speech_much_longer_than_fast | `1` |
| `R8007_M8011:30:2` | `new_runtime_proxy_window` | `runtime_proxy` | 17.237 | cross_model_disagreement_high;cross_model_segment_count_gap;cross_model_speaker_count_mismatch;pred_speech_too_long;slow_speech_much_longer_than_fast | `1` |
| `R8001_M8004:30:6` | `new_runtime_proxy_window` | `runtime_proxy` | 11.901 | cross_model_segment_count_gap;cross_model_speaker_count_mismatch;pred_speech_too_long;slow_speech_much_longer_than_fast | `1` |
| `R8001_M8004:30:8` | `new_runtime_proxy_window` | `runtime_proxy` | 9.021 | cross_model_speaker_count_mismatch;pred_speech_too_long;slow_speech_much_longer_than_fast | `1` |
| `R8008_M8013:30:8` | `new_runtime_proxy_window` | `runtime_proxy` | 7.196 | cross_model_segment_count_gap;cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8008_M8013:30:6` | `new_runtime_proxy_window` | `runtime_proxy` | 7.162 | cross_model_segment_count_gap;cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8007_M8011:30:8` | `new_runtime_proxy_window` | `runtime_proxy` | 6.955 | cross_model_segment_count_gap;cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8001_M8004:30:11` | `new_runtime_proxy_window` | `runtime_proxy` | 6.459 | cross_model_segment_count_gap;cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8007_M8011:30:1` | `new_runtime_proxy_window` | `runtime_proxy` | 6.250 | cross_model_segment_count_gap;cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8009_M8018:30:3` | `new_runtime_proxy_window` | `runtime_proxy` | 5.240 | cross_model_segment_count_gap;pred_speech_too_long | `1` |
| `R8009_M8020:30:12` | `new_runtime_proxy_window` | `runtime_proxy` | 4.895 | cross_model_segment_count_gap;pred_speech_too_long | `1` |
| `R8009_M8019:30:12` | `new_runtime_proxy_window` | `runtime_proxy` | 4.824 | cross_model_segment_count_gap;pred_speech_too_long | `1` |
| `R8009_M8018:30:11` | `new_runtime_proxy_window` | `runtime_proxy` | 4.821 | cross_model_segment_count_gap;pred_speech_too_long | `1` |
| `R8009_M8018:30:6` | `new_runtime_proxy_window` | `runtime_proxy` | 4.776 | cross_model_segment_count_gap;pred_speech_too_long | `1` |
| `R8007_M8010:30:1` | `new_runtime_proxy_window` | `runtime_proxy` | 4.736 | cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8008_M8013:30:13` | `new_runtime_proxy_window` | `runtime_proxy` | 4.713 | cross_model_segment_count_gap;pred_speech_too_long | `1` |
| `R8003_M8001:30:9` | `new_runtime_proxy_window` | `runtime_proxy` | 4.596 | cross_model_segment_count_gap;pred_speech_too_long | `1` |
| `R8007_M8010:30:7` | `new_runtime_proxy_window` | `runtime_proxy` | 4.235 | cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8009_M8019:30:7` | `new_runtime_proxy_window` | `runtime_proxy` | 4.216 | cross_model_segment_count_gap | `1` |
| `R8007_M8010:30:6` | `new_runtime_proxy_window` | `runtime_proxy` | 4.087 | cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8003_M8001:30:11` | `new_runtime_proxy_window` | `runtime_proxy` | 4.073 | cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8008_M8013:30:11` | `new_runtime_proxy_window` | `runtime_proxy` | 4.049 | cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8009_M8020:30:3` | `new_runtime_proxy_window` | `runtime_proxy` | 3.960 | cross_model_segment_count_gap | `1` |
| `R8007_M8010:30:13` | `new_runtime_proxy_window` | `runtime_proxy` | 3.953 | cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8007_M8010:30:8` | `new_runtime_proxy_window` | `runtime_proxy` | 3.915 | cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8007_M8010:30:3` | `new_runtime_proxy_window` | `runtime_proxy` | 3.837 | cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8003_M8001:30:8` | `new_runtime_proxy_window` | `runtime_proxy` | 3.769 | cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8003_M8001:30:14` | `new_runtime_proxy_window` | `runtime_proxy` | 3.707 | cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8007_M8011:30:11` | `new_runtime_proxy_window` | `runtime_proxy` | 3.675 | cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8003_M8001:30:7` | `new_runtime_proxy_window` | `runtime_proxy` | 3.603 | cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8003_M8001:30:0` | `new_runtime_proxy_window` | `runtime_proxy` | 3.581 | cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |
| `R8008_M8013:30:5` | `new_runtime_proxy_window` | `runtime_proxy` | 3.440 | cross_model_speaker_count_mismatch;pred_speech_too_long | `1` |

## Reading

- This manifest prepares the expanded Omni run; it does not perform live Omni/API calls.
- Existing 12-window smoke rows are retained as anchors; new windows come from deployable acoustic proxy flags.
- Omni output remains label/quarantine-priority only and does not receive timeline writeback rights.
