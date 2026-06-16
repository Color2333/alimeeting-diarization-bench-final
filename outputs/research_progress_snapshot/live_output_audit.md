# Live Output Audit

- Runtime contract: `live_output_audit_no_live_calls`
- Status: `pending_live_outputs`
- Surfaces: `3`
- Expected live calls: `382`
- Observed live output rows: `0`
- Successful live output rows: `0`
- Missing output surfaces: `3`
- Partial/invalid surfaces: `0`
- Claim-ready surfaces: `0`
- Live calls performed by auditor: `0`

| Surface | Kind | Expected | Observed | Success | Missing | P95 call | Status | Claim gate |
|---|---|---:|---:|---:|---:|---:|---|---|
| `deepseek_resume_after_top3` | `llm_split20_primary` | 139 | 0 | 0 | 139 | 0.0 | `missing_output` | `blocked_missing_output` |
| `qwen_full_backup` | `llm_split20_backup` | 147 | 0 | 0 | 147 | 0.0 | `missing_output` | `blocked_missing_output` |
| `omni48_label_only` | `omni_label_only` | 96 | 0 | 0 | 96 | 0.0 | `missing_output` | `blocked_missing_output` |

## Reading

- This audit reads live-output files only; it performs no LLM or Omni calls.
- A surface is claim-ready only after the expected calls are present, successful, non-duplicated, and parse cleanly.
- LLM surfaces still need downstream safety scoring before being promoted from output coverage to full latency/safety evidence.
- Omni48 still needs metric scoring after its label-only output is complete.
