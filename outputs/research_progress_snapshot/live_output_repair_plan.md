# Live Output Repair Plan

- Runtime contract: `live_output_repair_plan_no_live_calls_no_scoring`
- Status: `waiting_live_outputs`
- Repair rows: `3`
- Clean-run rows: `3`
- Skip-existing rerun rows: `0`
- Quarantine-required rows: `0`
- Scoring-ready rows: `0`
- Expected calls: `382`
- Missing calls: `382`
- Live calls performed by builder: `0`
- Scoring commands executed: `False`
- No new metric claim: `True`

| Surface | Priority | Output status | Repair action | Expected | Observed | Missing | Next step |
|---|---:|---|---|---:|---:|---:|---|
| `deepseek_resume_after_top3` | `P0` | `missing_output` | `clean_run_waiting_credentials_or_quota` | 139 | 0 | 139 | `run_live_command` |
| `qwen_full_backup` | `P1` | `missing_output` | `clean_run_waiting_credentials_or_quota` | 147 | 0 | 147 | `run_live_command` |
| `omni48_label_only` | `P1` | `missing_output` | `clean_run_waiting_credentials_or_quota` | 96 | 0 | 96 | `run_live_command` |

## Reading

- Missing outputs map to clean live runs using the audited command surface.
- Partial outputs with parse, duplicate, extra-call, or summary mismatch signals map to quarantine-before-rerun.
- Partial but structurally valid outputs map to skip-existing rerun for missing or failed calls.
- Complete outputs map to scoring commands; this plan itself executes no live or scoring command.
