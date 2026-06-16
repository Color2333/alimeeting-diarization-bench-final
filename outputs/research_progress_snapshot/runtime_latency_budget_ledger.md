# Runtime Latency Budget Ledger

- Runtime contract: `runtime_latency_budget_ledger_from_existing_artifacts`
- Status: `pass`
- Rows: `10`
- Claim-now rows: `4`
- Smoke-only rows: `2`
- Pending/blocked rows: `2`
- Offline budget rows: `1`
- Live calls performed by builder: `0`

## Ledger

| Stage | Surface | Avg | P95 | Wall | Target status | Claim status | Writeback |
|---|---|---:|---:|---:|---|---|---|
| `fast_first_output` | runtime_120_windows | 0.383s | 0.445s | n/a | `pass` | `claim_now_runtime` | `fast_provisional` |
| `rule_writeback` | runtime_120_windows | 24.647s | 28.334s | n/a | `pass` | `claim_now_runtime` | `bounded_timeline_writeback` |
| `runtime_safe_llm_guard` | 104_proxy_flagged_windows | 44.918s | 63.849s | n/a | `pass` | `claim_now_runtime_zero_harm` | `block_or_quarantine_only` |
| `llm_review_signal` | 4_review_cases | 46.097s | 55.800s | n/a | `pass` | `claim_now_memory_protection` | `memory_protection_only` |
| `omni_realtime_single_smoke` | single_8s_audio_clip | 0.744s | n/a | 1.356s | `pass` | `smoke_only_not_omni48_claim` | `label_only_no_timeline_writeback` |
| `split20_simulated_policy` | 104_proxy_flagged_windows_offline_model | 41.226s | 46.005s | n/a | `planning_only` | `offline_budget_only` | `none` |
| `split20_deepseek_top3_live_smoke` | 3_slowest_parent_windows_8_calls | n/a | n/a | 29.014s | `pass` | `supporting_smoke_only` | `block_or_quarantine_only` |
| `split20_deepseek_full_resume` | 101_pending_parent_windows_139_calls | n/a | n/a | 384.444s | `blocked_external` | `blocked_by_quota_or_missing_resume` | `block_or_quarantine_only` |
| `split20_qwen_backup_top45` | 2_parent_windows_4_calls | n/a | n/a | 44.024s | `backup_completed_slow` | `execution_fallback_only` | `block_or_quarantine_only` |
| `omni48_label_only_live` | 48_windows_96_calls | n/a | n/a | n/a | `blocked_missing_credentials` | `pending_omni48_live_outputs` | `label_only_no_timeline_writeback` |

## Reading

- Claim-now rows are runtime evidence already covered by validation; smoke rows cannot support full-surface claims.
- Offline split20 budget rows estimate latency only; they do not replace live wall-clock evidence.
- Pending live rows remain blocked by credentials, provider quota, or missing live outputs.
