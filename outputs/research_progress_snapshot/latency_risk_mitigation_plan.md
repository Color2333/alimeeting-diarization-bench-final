# Latency Risk Mitigation Plan

- Runtime contract: `latency_risk_mitigation_plan_no_live_calls`
- Status: `blocked_waiting_for_primary_live_resume`
- Actions: `6`
- P0 actions: `2`
- Blocked actions: `3`
- Fallback-only actions: `1`
- Stretch candidates: `1`
- Guard risk level: `tight_margin`
- Guard P95 margin: `1.151`
- Primary mitigation: `max20_resume`
- Primary resume calls: `139`
- Stretch candidate: `max15_reexport`
- Stretch export status: `pass`
- Stretch export prompts: `178`
- Stretch P95 gain vs primary: `3.311`
- Live calls performed by builder: `0`
- No new metric claim: `True`

## Actions

| Action | Priority | Type | Status | Boundary | Decision |
|---|---|---|---|---|---|
| `preserve_current_slo_with_guard_risk_tag` | `P0` | `preserve_current_claim` | `active_current_claim` | `preserve_existing_slo_no_new_metric_claim` | Keep current 4/4 claim-now SLO rows, but label runtime-safe LLM guard as tight-margin. |
| `deepseek_max20_resume_primary` | `P0` | `primary_latency_mitigation` | `blocked_waiting_credentials_quota_or_live_output` | `blocked_until_full_surface_live_output_and_scoring` | Run DeepSeek max20 resume first: 139 calls / 101 parents after top3. |
| `max15_stretch_reexport` | `P1` | `stretch_latency_candidate` | `prepared_export_audited_waiting_live_output` | `stretch_plan_no_new_metric_claim` | Keep max15 ready as a stretch comparison: 178 exported calls, simulated P95 18.047s. |
| `qwen_backup_not_primary_latency` | `P1` | `fallback_boundary` | `fallback_only` | `fallback_only_not_primary_latency_claim` | Keep Qwen backup as execution/safety fallback, not as primary latency mitigation. |
| `omni48_label_only_not_guard_latency` | `P1` | `scope_boundary` | `blocked_waiting_omni48_live_outputs` | `label_only_no_timeline_writeback` | Keep Omni48 as label-only risk tagging; do not use it as timeline writeback or guard latency mitigation. |
| `selector_true_heldout_not_latency_mitigation` | `P1` | `scope_boundary` | `blocked_waiting_valid_sealed_split` | `data_generalization_not_latency_claim` | Keep selector true-heldout as generalization evidence, not as a guard latency mitigation path. |

## Reading

- This plan converts the guard tight-margin audit into ordered next actions.
- `max20_resume` stays the primary mitigation because it has exported prompts, top3 smoke evidence, and a resume surface.
- `max15_reexport` is a stretch candidate only after provider quota/capacity is stable.
- Qwen, Omni48, and selector true-heldout remain useful surfaces, but they do not support a primary guard-latency mitigation claim today.
- The builder only reads local artifacts; it performs no live/API/model calls and writes no secrets.
