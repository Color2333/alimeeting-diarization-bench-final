# Live Resume State Audit

- Runtime contract: `live_resume_state_audit_no_live_calls`
- Status: `clean_run_ready_waiting_credentials_or_quota`
- Clean-run surfaces: `3` / `3`
- Current commands safe to run: `3`
- P0 current commands safe to run: `1`
- Partial/invalid surfaces: `0`
- Completed output surfaces: `0`
- Append resume supported surfaces: `0`
- Skip-existing supported surfaces: `3`
- Bounded-retry supported surfaces: `3`
- Quarantine required surfaces: `0`
- Planned live calls: `382`
- Missing live calls: `382`
- Live calls performed by builder: `0`
- No new metric claim: `True`

| Surface | Command | State | Calls | Safe now | Action | Claim gate |
|---|---|---|---:|---|---|---|
| `deepseek_resume_after_top3` | `deepseek_resume_primary` | `missing_output_clean_run` | 139 | `True` | `run_current_command_when_credentials_and_quota_are_ready` | `blocked_missing_output` |
| `qwen_full_backup` | `qwen_full_backup_optional` | `missing_output_clean_run` | 147 | `True` | `run_current_command_when_credentials_and_quota_are_ready` | `blocked_missing_output` |
| `omni48_label_only` | `omni48_label_only_live` | `missing_output_clean_run` | 96 | `True` | `run_current_command_when_credentials_and_quota_are_ready` | `blocked_missing_output` |

## Reading

- This audit is a no-live-call recovery decision table for pending live outputs.
- The current LLM and Omni runners reuse successful existing rows with `--skip-existing-output`, then overwrite a complete merged JSONL/CSV.
- They use bounded retry (`--max-call-attempts 2 --retry-backoff-seconds 2.0`) for transient call failures.
- They still do not append blindly; failed or invalid rows are rerun, while successful rows can be preserved.
- When an output is missing, the current command is safe as a clean run after credentials and quota are available.
- When a partial output appears, prefer `--skip-existing-output`; quarantine/archive invalid rows first if parsing or duplicate-id checks fail.
- Command-safe and resume-state-ready are not metric claims; output audit, scoring, SLO, promotion, and traceability gates must still pass.
