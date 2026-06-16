# Phase Result Scorecard

- Runtime contract: `phase_result_scorecard_from_existing_artifacts_no_live_calls`
- Status: `pass`
- Result rows: `8`
- Claim-now SLO pass: `4/4`
- Selector positive splits: `8/8`
- Selector weighted DER delta: `2.05` pp
- Rule bootstrap DER delta: `2.17` pp
- Guard harmful accepts: `0`
- Guard safe accepts: `323`
- Omni smoke windows: `12`
- Qwen fallback calls: `4`
- DeepSeek API calls: `0` (no-go after exhaustion)
- Traceability: `54/54`

| Area | Result | Metric | Evidence | Boundary |
|---|---|---|---|---|
| DER improvement | Selector improves DER on all recording-holdout splits. | 28.56% -> 26.51% (+2.05 pp); positive splits 8/8 | `recording_holdout` | `not_true_heldout_until_new_recordings` |
| DER improvement | Rule-recover policy beats fast baseline in bootstrap sampling. | fast 28.56% vs rule 26.40%; delta +2.17 pp; P(beats fast) 100.0% | `development_bootstrap` | `dev_set_not_final_test` |
| DER reference | Slow model is the quality upper reference but not the realtime path. | slow 16.88% vs fast 28.56%; delta +11.68 pp | `development_bootstrap` | `quality_reference_not_realtime_claim` |
| Latency | Current claim-now runtime stages pass latency SLO. | 4/4; fast avg/p95 0.383/0.445s; writeback avg/p95 24.647/28.334s | `claim_now_runtime` | `post_live_latency_not_claimed` |
| Safety | Runtime-safe guard recovers useful patches while preserving zero harmful accepts. | safe accepts 323; harmful accepts 0; conservative recovered 260; patches 1917 | `runtime_guard_existing_outputs` | `block_or_quarantine_only_no_auto_timeline_override` |
| Acoustic / Omni | Omni acoustic signal is useful for review routing, not direct writeback. | high recall 4/4 (100.0%); clean high-sentinel FP 0/4 (0.0%); flash avg/p95 2.11/6.41s | `12_window_smoke` | `label_only_no_timeline_writeback` |
| Fallback live smoke | Qwen fallback completed safely but is slower than the primary latency target. | parents 2; calls 4; wall 44.024s; harmful accepts 0 | `fallback_smoke` | `fallback_only_not_primary_latency_claim` |
| Execution decision | DeepSeek full-live path is no-go after API exhaustion. | observed live rows 0; missing surfaces 3; DeepSeek API exhausted, no further DeepSeek calls | `execution_boundary` | `do_not_use_deepseek_api` |

## Reading

- The strongest current result is not a completed live-agent run; it is a validated staged system result: DER improves on recording-holdout selector evidence, claim-now runtime stages pass SLO, and guard safety preserves zero harmful accepts.
- DeepSeek full-live is explicitly no-go after API exhaustion; this scorecard performs no live/API/model/scoring calls.
- Qwen and Omni are currently fallback/smoke or label-only evidence. They should be used to tell the next-step route, not to overclaim full-surface live performance.
