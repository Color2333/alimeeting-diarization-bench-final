# Post-Live Claim Promotion Gate

- Runtime contract: `post_live_claim_promotion_gate_no_live_calls`
- Status: `pass`
- Promotion policy: `promote_only_after_output_audit_scoring_slo_and_traceability_pass`
- Gates: `8`
- Ready to promote: `0`
- Blocked: `5`
- Preserve/current sync gates: `2`
- Fallback-only gates: `1`
- Missing source rows: `0`
- Live calls performed by builder: `0`
- No new metric claim: `True`

## Gates

| Gate | Claim surface | Decision | Blocking gate | Observed state | Next action |
|---|---|---|---|---|---|
| `current_latency_slo_claims` | current reportable latency SLO rows | `preserve_current_claim` | `none` | 4/4 SLO pass; guard risk tight_margin | preserve while post-live rows remain pending |
| `deepseek_split20_resume_latency` | DeepSeek split20 104-window full-surface latency | `blocked_missing_live_output` | `blocked_by_quota_or_missing_resume` | resume expected 139 calls; successful 0; missing output surfaces 3 | run P0 DeepSeek max20 resume after credentials/quota are ready |
| `deepseek_split20_resume_safety` | DeepSeek split20 resume zero-harm safety | `blocked_waiting_scoring` | `blocked_missing_output` | ready to score 0/5; P0 scoring steps 2 | wait for resume JSONL, then run planned safety scoring command |
| `omni48_label_metrics` | Omni48 label-only recall/precision/latency | `blocked_missing_live_output` | `pending_omni48_live_outputs` | expected 96 calls; successful 0 | run Omni48 label-only live calls after credentials are present |
| `qwen_full_backup_claim` | Qwen full-surface backup LLM guard | `fallback_only_not_primary_latency_claim` | `backup surface missing and prior top4/5 wall slower than original max` | backup expected 147 calls; split policy primary max20 | keep as P1 fallback after DeepSeek primary path |
| `selector_true_heldout_claim` | selector true-heldout generalization | `blocked_waiting_valid_sealed_split` | `blocked_waiting_for_valid_sealed_split` | true-heldout recordings 0; missing new recordings 8 | add a sealed split with new recordings before scoring |
| `live_execution_handoff` | operator handoff for live LLM/Omni execution | `blocked_waiting_credentials_or_outputs` | `blocked_waiting_for_credentials_or_live_outputs` | runbook steps 7; P0 planned calls 139; ready runs 0 | start from runbook step 1 when credentials/quota are available |
| `report_ppt_sync_after_promotion` | report/PPT synchronization after any claim promotion | `preserve_sync_gate` | `none` | fully covered 54/54 | rerun refresh after any live output/scoring artifact appears |

## Reading

- A gate can become `ready_to_promote` only after live output coverage, scoring readiness/results, SLO status, and report/PPT traceability all pass.
- Current reportable claims are preserved, while post-live DeepSeek, Omni48, and true-heldout selector claims remain blocked or pending.
- This builder only reads local artifacts; it writes no secrets and performs no live/API/model calls.
