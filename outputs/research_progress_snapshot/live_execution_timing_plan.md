# Live Execution Timing Plan

- Runtime contract: `live_execution_timing_plan_no_live_calls`
- Status: `blocked_waiting_for_credentials_or_live_outputs`
- Timing rows: `6`
- P0 / P1 rows: `4` / `2`
- DeepSeek resume calls: `139`
- DeepSeek workers / waves: `8` / `18`
- DeepSeek estimated wall: `384.444`
- Qwen estimated wall: `836.456`
- Omni48 label-only calls: `96`
- Unknown wall rows: `3`
- Live calls performed by builder: `0`
- No new metric claim: `True`

| Timing | Priority | Phase | Calls | Workers | Waves | Wall estimate | Claim status | Blocking state |
|---|---|---|---:|---:|---:|---:|---|---|
| `credential_preflight` | `P0` | `preflight` | 0 | 0 | 0 | 0.0 | `gate_only_no_latency_claim` | `blocked_missing_credentials` |
| `deepseek_max20_resume_live_call` | `P0` | `primary_live_call` | 139 | 8 | 18 | 384.444 | `not_claimable_until_resume_output_and_scoring` | `blocked_by_provider_quota_or_capacity` |
| `deepseek_postrun_audit_and_scoring` | `P0` | `postrun_scoring` | 0 | 0 | 0 | n/a | `not_claimable_until_output_audit_and_safety_comparison_pass` | `blocked_waiting_live_outputs` |
| `omni48_label_only_live` | `P1` | `label_only_live_call` | 96 | 0 | 0 | n/a | `label_only_not_timeline_writeback_not_guard_latency_claim` | `blocked_missing_credentials` |
| `qwen_full_backup_optional` | `P1` | `fallback_live_call` | 147 | 8 | 19 | 836.456 | `fallback_only_not_primary_latency_claim` | `blocked_missing_credentials` |
| `refresh_report_ppt_validation` | `P0` | `refresh_and_validate` | 0 | 0 | 0 | n/a | `validation_only` | `waiting_for_live_outputs` |

## Reading

- This artifact separates live-call wall estimates from reportable latency claims.
- DeepSeek max20 resume is the P0 timed path: 139 calls, 8 workers, 18 waves, 384.444s estimated wall from simulated P95.
- Qwen backup is slower and fallback-only; Omni48 has clip-model seconds but still needs live first-text and total latency measurement.
- Postrun scoring and refresh are validation steps, not live latency claims.
- The builder only reads local artifacts; it performs no live/API/model calls and writes no secrets.
