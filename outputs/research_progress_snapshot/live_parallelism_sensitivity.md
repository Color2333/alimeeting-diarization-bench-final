# Live Parallelism Sensitivity

- Runtime contract: `live_parallelism_sensitivity_no_live_calls`
- Status: `planning_only_blocked_waiting_for_credentials_or_quota`
- Rows: `20`
- Policies / worker counts: `5` / `4`
- Recommended policy/workers: `max20` / `8`
- Recommended estimated wall: `384.444`
- Recommended waves: `18`
- max20 worker12 estimated wall: `256.296`
- max20 worker12 wall gain: `128.148`
- Stretch max15 workers8 estimated wall: `415.081`
- Live calls performed by builder: `0`
- No new metric claim: `True`

| Policy | Role | Workers | Calls | Waves | P95 call | Wall estimate | Token x | Risk | Recommendation |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| `max20` | `resume_primary` | 4 | 139 | 35 | 21.358 | 747.53 | 1.118 | `low_burst_slow_wall` | `safe_but_slower_fallback` |
| `max20` | `resume_primary` | 8 | 139 | 18 | 21.358 | 384.444 | 1.118 | `current_runbook_default` | `recommended_p0_default` |
| `max20` | `resume_primary` | 12 | 139 | 12 | 21.358 | 256.296 | 1.118 | `medium_burst_needs_provider_stability` | `speedup_candidate_after_quota_stable` |
| `max20` | `resume_primary` | 16 | 139 | 9 | 21.358 | 192.222 | 1.118 | `high_burst_exploratory_only` | `speedup_candidate_after_quota_stable` |
| `max15` | `latency_stretch_reexport` | 4 | 178 | 45 | 18.047 | 812.115 | 1.182 | `low_burst_slow_wall` | `stretch_reexport_only` |
| `max15` | `latency_stretch_reexport` | 8 | 178 | 23 | 18.047 | 415.081 | 1.182 | `current_runbook_default` | `stretch_reexport_only` |
| `max15` | `latency_stretch_reexport` | 12 | 178 | 15 | 18.047 | 270.705 | 1.182 | `medium_burst_needs_provider_stability` | `stretch_reexport_only` |
| `max15` | `latency_stretch_reexport` | 16 | 178 | 12 | 18.047 | 216.564 | 1.182 | `high_burst_exploratory_only` | `stretch_reexport_only` |
| `max12` | `exploratory_low_latency_high_cost` | 8 | 209 | 27 | 16.19 | 437.13 | 1.246 | `current_runbook_default` | `exploratory_high_quota_cost` |
| `max12` | `exploratory_low_latency_high_cost` | 12 | 209 | 18 | 16.19 | 291.42 | 1.246 | `medium_burst_needs_provider_stability` | `exploratory_high_quota_cost` |
| `max10` | `exploratory_low_latency_high_cost` | 8 | 239 | 30 | 15.081 | 452.43 | 1.307 | `current_runbook_default` | `exploratory_high_quota_cost` |
| `max10` | `exploratory_low_latency_high_cost` | 12 | 239 | 20 | 15.081 | 301.62 | 1.307 | `medium_burst_needs_provider_stability` | `exploratory_high_quota_cost` |
| `max8` | `exploratory_low_latency_high_cost` | 8 | 286 | 36 | 13.647 | 491.292 | 1.404 | `current_runbook_default` | `exploratory_high_quota_cost` |
| `max8` | `exploratory_low_latency_high_cost` | 12 | 286 | 24 | 13.647 | 327.528 | 1.404 | `medium_burst_needs_provider_stability` | `exploratory_high_quota_cost` |

## Reading

- Keep `max20` with 8 workers as the P0 default because it matches the exported resume surface and current runbook.
- `max20` with 12 workers could reduce the estimated wall by 128.148s, but it raises burst pressure and should wait for provider stability.
- `max15` at 8 workers is faster than `max20` at 8 workers, but it requires a fresh export and cannot reuse max20 top3 evidence.
- All rows are planning estimates only; no live/API/model calls are performed and no new latency metric is claimed.
