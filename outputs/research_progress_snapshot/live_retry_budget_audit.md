# Live Retry Budget Audit

- Runtime contract: `live_retry_budget_audit_no_live_calls`
- Status: `retry_budget_ready_waiting_credentials_or_quota`
- Surfaces: `3`
- Bounded-retry surfaces: `3`
- Planned live calls: `382`
- Max attempted requests: `764`
- Additional retry attempt budget: `382`
- Backoff ceiling seconds: `764.0`
- P0 max attempted requests: `278`
- DeepSeek retry ceiling wall: `804.888`
- DeepSeek retry wall overhead: `420.444`
- Live calls performed by builder: `0`
- No new metric claim: `True`

| Command | Priority | Calls | Attempts | Max requests | Backoff ceiling | Workers | Waves | Per-attempt wall | Retry ceiling wall |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `deepseek_resume_primary` | `P0` | 139 | 2 | 278 | 278.0 | 8 | 18 | 384.444 | 804.888 |
| `omni48_label_only_live` | `P1` | 96 | 2 | 192 | 192.0 | 0 | 0 | n/a | n/a |
| `qwen_full_backup_optional` | `P1` | 147 | 2 | 294 | 294.0 | 8 | 19 | 836.456 | 1710.912 |

## Reading

- This audit turns bounded retry into an explicit attempt and wall-time ceiling before any live run starts.
- The 382 planned live calls can become at most 764 attempted requests under the current 2-attempt command policy.
- P0 DeepSeek max20 remains the first run, but retry ceiling wall is a planning ceiling, not a reportable latency metric.
- Omni48 still has no live first-text/total latency; this audit only counts its attempt budget.
- The builder only reads local artifacts; it performs no live/API/model calls and writes no secrets.
