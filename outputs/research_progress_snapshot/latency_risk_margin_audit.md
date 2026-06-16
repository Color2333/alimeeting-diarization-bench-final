# Latency Risk Margin Audit

- Runtime contract: `latency_risk_margin_audit_from_slo_no_live_calls`
- Status: `pass`
- Claim-now rows: `4`
- Tight-margin rows: `1`
- Watch rows: `0`
- Blocked rows: `2`
- Non-claimable rows: `4`
- Guard risk level: `tight_margin`
- Guard P95 margin: `1.151`
- Guard P95 margin ratio: `0.0177`
- Post-live ready to promote: `0`
- Live calls performed by builder: `0`
- No new metric claim: `True`

## Risk Rows

| Stage | SLO class | Risk | P95 | P95 margin | Margin ratio | Promotion impact | Watch action |
|---|---|---|---:|---:|---:|---|---|
| `fast_first_output` | `claim_now_slo_pass` | `comfortable` | 0.445 | 0.555 | 0.555 | preserve claim-now latency | preserve current claim |
| `rule_writeback` | `claim_now_slo_pass` | `comfortable` | 28.334 | 6.666 | 0.1905 | preserve bounded writeback claim | preserve current claim |
| `runtime_safe_llm_guard` | `claim_now_slo_pass` | `tight_margin` | 63.849 | 1.151 | 0.0177 | preserve but watch before post-live promotion | prioritize split20 resume or smaller max-patch policy before claiming broader guard latency |
| `llm_review_signal` | `claim_now_slo_pass` | `claim_current_no_threshold` | 55.8 | n/a | n/a | preserve review/memory-protection timing | review before report promotion |
| `omni_realtime_single_smoke` | `smoke_slo_pass` | `smoke_only` | n/a | n/a | n/a | do not promote to Omni48 claim | keep as smoke/supporting evidence only |
| `split20_simulated_policy` | `offline_budget_only` | `planning_only` | 46.005 | n/a | n/a | planning input for DeepSeek resume only | use as run planning evidence only |
| `split20_deepseek_top3_live_smoke` | `smoke_slo_pass` | `smoke_only` | n/a | n/a | n/a | supporting smoke; not full-surface claim | keep as smoke/supporting evidence only |
| `split20_deepseek_full_resume` | `pending_or_blocked` | `blocked` | n/a | n/a | n/a | blocked until resume output and scoring exist | wait for credentials, live output, and scoring |
| `split20_qwen_backup_top45` | `fallback_only` | `fallback_only` | n/a | n/a | n/a | fallback-only execution evidence | keep out of primary latency claim |
| `omni48_label_only_live` | `pending_or_blocked` | `blocked` | n/a | n/a | n/a | blocked until 96-call live output exists | wait for credentials, live output, and scoring |

## Reading

- This audit turns SLO margin into risk labels for report-level latency claims.
- `tight_margin` keeps a current claim valid, but marks it as sensitive to future live-output latency drift.
- Smoke, planning, fallback, and blocked rows stay out of claim-now latency until their promotion gates pass.
- This builder reads existing artifacts only; it performs no live/API/model calls and creates no new metric claim.
