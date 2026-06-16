# Stage Latency SLO Audit

- Runtime contract: `stage_latency_slo_audit_from_latency_ledger_no_live_calls`
- Status: `pass`
- Claim-now SLO pass: `4/4`
- Smoke rows: `2`
- Pending/blocked rows: `2`
- Min claim P95 margin: `0.555`
- Guard P95 margin: `1.151`
- Live calls performed by builder: `0`
- No new metric claim: `True`

| Stage | Claim status | SLO class | Avg | P95 | Wall | Target | P95 margin |
|---|---|---|---:|---:|---:|---|---:|
| `fast_first_output` | `claim_now_runtime` | `claim_now_slo_pass` | 0.383 | 0.445 | n/a | `avg<=1s_and_p95<=1s` | 0.555 |
| `rule_writeback` | `claim_now_runtime` | `claim_now_slo_pass` | 24.647 | 28.334 | n/a | `avg<=30s_and_p95<=35s` | 6.666 |
| `runtime_safe_llm_guard` | `claim_now_runtime_zero_harm` | `claim_now_slo_pass` | 44.918 | 63.849 | n/a | `avg<=50s_and_p95<=65s` | 1.151 |
| `llm_review_signal` | `claim_now_memory_protection` | `claim_now_slo_pass` | 46.097 | 55.8 | n/a | `review_only_no_timeline_override` | n/a |
| `omni_realtime_single_smoke` | `smoke_only_not_omni48_claim` | `smoke_slo_pass` | 0.744 | n/a | 1.356 | `first_text<1s_total<2s` | n/a |
| `split20_simulated_policy` | `offline_budget_only` | `offline_budget_only` | 41.226 | 46.005 | n/a | `planning_only_no_live_claim` | n/a |
| `split20_deepseek_top3_live_smoke` | `supporting_smoke_only` | `smoke_slo_pass` | n/a | n/a | 29.014 | `wall<original_max_on_top3` | n/a |
| `split20_deepseek_full_resume` | `blocked_by_quota_or_missing_resume` | `pending_or_blocked` | n/a | n/a | 384.444 | `needs_live_resume_output_before_claim` | n/a |
| `split20_qwen_backup_top45` | `execution_fallback_only` | `fallback_only` | n/a | n/a | 44.024 | `backup_only_not_latency_supporting` | n/a |
| `omni48_label_only_live` | `pending_omni48_live_outputs` | `pending_or_blocked` | n/a | n/a | n/a | `needs_96_call_live_output` | n/a |

## Reading

- This audit derives SLO status from the latency ledger; it performs no model calls and creates no new metric claim.
- Claim-now rows must pass their explicit SLO targets before they can be used as report-level latency claims.
- Smoke rows can support readiness or routing evidence, but not full-surface claims.
- Pending/blocked rows remain excluded from claim-now latency until live outputs and scoring artifacts exist.
