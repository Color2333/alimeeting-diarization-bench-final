# Realtime Batch Consistency Audit

- Runtime contract: `offline_realtime_batch_consistency_no_live_calls`
- Status: `pass`
- Checks: `9` pass, `0` warn, `0` fail
- Batch weighted final DER: `16.4923%`
- Corpus final DER: `16.4923%`
- Absolute DER gap: `0.000000pp`

| Status | Code | Message |
|---|---|---|
| `pass` | `batch_summary_exists` | all-cached batch summary exists |
| `pass` | `batch_status_pass` | all-cached batch completed with pass status |
| `pass` | `all_recordings_processed` | all expected cached recordings are processed and passed |
| `pass` | `all_windows_processed` | all expected cached windows are processed |
| `pass` | `all_item_timeline_integrity_pass` | every batch item passed timeline integrity |
| `pass` | `batch_zero_live_api_calls` | all-cached batch performs zero live API calls |
| `pass` | `batch_uses_window_weighted_aggregation` | batch summary reports corpus DER using window-weighted aggregation rather than item-average aggregation |
| `pass` | `batch_reported_der_is_weighted` | reported batch final DER equals recomputed window-weighted final DER |
| `pass` | `batch_der_matches_corpus_demo` | weighted batch final DER matches corpus-level all-cached demo DER |

## Per Recording

| Recording | Status | Windows | Final DER | Timeline |
|---|---|---:|---:|---|
| `R8001_M8004` | `pass` | 15 | 17.92% | `pass` |
| `R8003_M8001` | `pass` | 15 | 35.89% | `pass` |
| `R8007_M8010` | `pass` | 15 | 24.35% | `pass` |
| `R8007_M8011` | `pass` | 15 | 15.88% | `pass` |
| `R8008_M8013` | `pass` | 15 | 16.67% | `pass` |
| `R8009_M8018` | `pass` | 15 | 10.30% | `pass` |
| `R8009_M8019` | `pass` | 15 | 5.65% | `pass` |
| `R8009_M8020` | `pass` | 15 | 5.28% | `pass` |
