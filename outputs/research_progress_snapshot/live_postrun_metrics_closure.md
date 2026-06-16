# Live Postrun Metrics Closure

- Runtime contract: `live_postrun_metrics_closure_no_live_calls`
- Status: `pending_live_outputs`
- Split20 expected calls: `147`
- DeepSeek success calls: `8`
- DeepSeek resume expected calls: `139`
- DeepSeek quota-failed calls: `4`
- Split20 latency claim status: `blocked_by_quota_or_missing_resume`
- Omni48 expected calls: `96`
- Omni48 successful calls: `0`
- Omni48 latency claim status: `pending_omni48_live_outputs`
- Omni realtime single-smoke latency: `0.744` first text / `1.356` total
- Live calls performed by builder: `0`

## Surfaces

| Surface | Kind | Expected | Observed | Success | Failed | Status | Claim status |
|---|---|---:|---:|---:|---:|---|---|
| `deepseek_top3_parallel_smoke` | `llm_split20` | 8 | 8 | 8 | 0 | `completed_limited_smoke` | `supporting_smoke_only` |
| `deepseek_top4_5_quota_attempt` | `llm_split20` | 4 | 4 | 0 | 4 | `failed_AllocationQuota.FreeTierOnly` | `blocking_full_surface_claim` |
| `deepseek_resume_after_top3` | `llm_split20` | 139 | 0 | 0 | 0 | `pending_live_output` | `blocked_by_quota_or_missing_resume` |
| `qwen_top4_5_backup` | `llm_split20_backup` | 4 | 4 | 4 | 0 | `completed_backup_not_latency_supporting` | `execution_fallback_only` |
| `qwen_full_backup` | `llm_split20_backup` | 147 | 0 | 0 | 0 | `pending_live_output` | `fallback_only_not_primary_latency_claim` |
| `omni48_label_only` | `omni_label_only` | 96 | 0 | 0 | 0 | `pending_live_output` | `pending_omni48_live_outputs` |
| `omni_realtime_single_smoke` | `omni_realtime_smoke` | 1 | 1 | 1 | 0 | `completed_single_latency_smoke` | `smoke_only_not_omni48_claim` |

## Reading

- This artifact is a postrun closure checker; it performs no live LLM/Omni calls.
- Current DeepSeek evidence is limited to the top3 live smoke plus a quota-failed top4/top5 attempt.
- Full split20 latency remains unclaimed until the resume output exists and covers the remaining 139 calls.
- Omni48 first-text and total latency remain unclaimed until the 96-call label-only expansion output exists.
