# Post-Live Latency Claim Matrix

- Runtime contract: `post_live_latency_claim_matrix_no_live_calls`
- Status: `blocked_waiting_live_outputs`
- Latency claim rows: `8`
- P0 / P1 rows: `6` / `2`
- Claim-now preserve rows: `4`
- Blocked/waiting rows: `4`
- Fallback-only rows: `1`
- Label-only rows: `1`
- Tight-margin rows: `1`
- Claim-now SLO pass: `4/4`
- Guard P95 margin seconds: `1.151`
- Expected live calls: `382`
- Missing output surfaces: `3`
- DeepSeek estimated wall seconds: `384.444`
- Qwen estimated wall seconds: `836.456`
- Omni48 label-only calls: `96`
- Ready to promote: `0`
- Traceability rows: `54`
- Live calls performed by builder: `0`
- No new metric claim: `True`

| Claim | Priority | Surface | State | Metric/budget | Promotion gate | Boundary |
|---|---|---|---|---|---|---|
| `fast_first_output_current` | `P0` | `runtime_120_windows` | `claim_now_preserve` | avg 0.383s / p95 0.445s | `current_claim_now_slo` | `claim_now_latency_preserve` |
| `rule_writeback_current` | `P0` | `runtime_120_windows` | `claim_now_preserve` | avg 24.647s / p95 28.334s | `current_claim_now_slo` | `claim_now_latency_preserve` |
| `runtime_safe_guard_current` | `P0` | `104_proxy_flagged_windows` | `claim_now_preserve_with_tight_margin_watch` | avg 44.918s / p95 63.849s / margin 1.151s | `current_claim_now_slo_and_risk_watch` | `claim_now_latency_preserve_no_broader_claim` |
| `llm_review_signal_current` | `P0` | `4_review_cases` | `claim_now_memory_protection_preserve` | avg 46.097s / p95 55.8s | `current_claim_now_review_only` | `review_only_no_timeline_override` |
| `deepseek_split20_full_surface` | `P0` | `104_parent_windows_147_split_calls` | `blocked_waiting_live_outputs` | planned resume 139 calls / estimated wall 384.444s | `deepseek_split20_resume_latency` | `not_claimable_until_resume_output_audit_scoring_and_traceability` |
| `omni48_label_latency` | `P1` | `48_windows_96_calls` | `blocked_waiting_live_outputs` | clip-model seconds proxy 768.0; first-text/total latency pending | `omni48_label_metrics` | `label_only_latency_not_guard_or_timeline_claim` |
| `qwen_full_backup_latency` | `P1` | `104_parent_windows_147_split_calls` | `fallback_only_waiting_credentials` | fallback budget 836.456s | `qwen_full_backup_claim` | `fallback_only_not_primary_latency_claim` |
| `report_ppt_latency_sync` | `P0` | `report_ppt` | `waiting_post_live_promotion` | traceability 54/54 | `report_ppt_traceability_after_promotion` | `report_ppt_sync_required_before_latency_claim_promotion` |

## Reading

- This matrix separates current reportable latency claims from post-live claim candidates.
- DeepSeek split20 can become full-surface latency evidence only after live output audit, safety scoring, comparison, and traceability pass.
- Omni48 latency remains label-only; Qwen remains fallback-only unless a later promotion gate changes the boundary.
- The builder reads local artifacts only; it performs no live/API/model/scoring calls and writes no secrets.
