# Omni48 Live Call Manifest

- Runtime contract: `omni48_live_call_manifest_no_live_calls_label_only`
- Status: `pass`
- Source windows: `48`
- Omni48 call manifest: `96` calls / expected `96`
- Target models: `qwen3.5-omni-flash; qwen3.5-omni-plus-2026-03-15`
- Anchor smoke calls: `24`
- New runtime-proxy calls: `72`
- Audio missing: `0`
- Clip audio seconds: `384.0`
- Clip model seconds proxy: `768.0`
- Live calls performed: `0`
- Writeback right: `label_only_no_timeline_writeback`
- No timeline writeback: `True`
- Output JSONL: `outputs/omni_guard/omni_expansion_48_live.jsonl`

## Run Command

```bash
python scripts/omni_guard_window_batch.py --input-windows-csv outputs/research_progress_snapshot/omni_expansion_manifest.csv --model qwen3.5-omni-flash --model qwen3.5-omni-plus-2026-03-15 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/omni_guard/omni_expansion_48_live.jsonl
```

## First Calls

| # | Window | Model | Role | Audio | Writeback |
|---:|---|---|---|---|---|
| 1 | `R8001_M8004:30:1` | `qwen3.5-omni-flash` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 2 | `R8001_M8004:30:1` | `qwen3.5-omni-plus-2026-03-15` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 3 | `R8001_M8004:30:3` | `qwen3.5-omni-flash` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 4 | `R8001_M8004:30:3` | `qwen3.5-omni-plus-2026-03-15` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 5 | `R8001_M8004:30:5` | `qwen3.5-omni-flash` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 6 | `R8001_M8004:30:5` | `qwen3.5-omni-plus-2026-03-15` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 7 | `R8003_M8001:30:3` | `qwen3.5-omni-flash` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 8 | `R8003_M8001:30:3` | `qwen3.5-omni-plus-2026-03-15` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 9 | `R8003_M8001:30:4` | `qwen3.5-omni-flash` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 10 | `R8003_M8001:30:4` | `qwen3.5-omni-plus-2026-03-15` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 11 | `R8003_M8001:30:5` | `qwen3.5-omni-flash` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 12 | `R8003_M8001:30:5` | `qwen3.5-omni-plus-2026-03-15` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 13 | `R8007_M8010:30:4` | `qwen3.5-omni-flash` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 14 | `R8007_M8010:30:4` | `qwen3.5-omni-plus-2026-03-15` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 15 | `R8007_M8011:30:0` | `qwen3.5-omni-flash` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |
| 16 | `R8007_M8011:30:0` | `qwen3.5-omni-plus-2026-03-15` | `anchor_smoke_window` | `1` | `label_only_no_timeline_writeback` |

## Reading

- This artifact expands the 48-window Omni manifest into per-model call rows only.
- It does not call any model and does not read or write live Omni responses.
- Every planned call is label-only and has no timeline writeback right.
