# External Candidate Source Inventory

- Runtime contract: `external_candidate_source_inventory_no_live_calls_gt_fingerprint_filtered`
- Status: `pass`
- Sources scanned: `4`
- Sources with valid windows: `3`
- Full-coverage clean sources: `3`
- Sources with stale GT mismatch: `0`
- Non-positive recordings: `R8001_M8004, R8008_M8013, R8009_M8020`

## Top Sources

| Source | Valid | Stale | Missing | Wins/Losses | Mean Delta | Non-positive Delta |
|---|---:|---:|---:|---:|---:|---:|
| `outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json` | 120 | 0 | 0 | 13/30 | -0.3886pp | -0.0011pp |
| `outputs/diarizen_uv_48/diarizen-large-v2/default__spk_none/summary.json` | 120 | 0 | 0 | 13/30 | -0.3886pp | -0.0011pp |
| `outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json` | 120 | 0 | 0 | 1/115 | -12.0714pp | -16.8204pp |

## Reading

- Valid windows match the current runtime pool by recording/window key and GT fingerprint.
- Stale windows share a key but belong to a different sampled segment; they must not be used for promotion or policy search.
- Sources with weak non-positive-recording delta are poor candidates for improving recording-level robustness.
