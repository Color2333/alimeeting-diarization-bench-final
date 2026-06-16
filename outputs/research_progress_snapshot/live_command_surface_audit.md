# Live Command Surface Audit

- Runtime contract: `live_command_surface_audit_no_live_calls`
- Secret policy: `commands_scanned_no_secret_values_written`
- Status: `commands_ready_waiting_credentials_or_quota`
- Command-ready: `3` / `3`
- P0 command-ready: `1`
- Planned live calls: `382`
- P0 planned live calls: `139`
- Missing-input commands: `0`
- Duplicate output paths: `0`
- Skip-existing commands: `3`
- Bounded-retry commands: `3`
- Secret literal commands: `0`
- Live calls performed by builder: `0`
- No new metric claim: `True`

| Command | Priority | Kind | Calls | Ready | Inputs missing | Output | Writeback |
|---|---|---|---:|---|---|---|---|
| `deepseek_resume_primary` | `P0` | `llm_window_batch_policy_eval` | 139 | `True` | none | `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl` | `block_or_quarantine_only` |
| `omni48_label_only_live` | `P1` | `omni_guard_window_batch` | 96 | `True` | none | `outputs/omni_guard/omni_expansion_48_live.jsonl` | `label_only_no_timeline_writeback` |
| `qwen_full_backup_optional` | `P1` | `llm_window_batch_policy_eval` | 147 | `True` | none | `outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl` | `block_or_quarantine_only` |

## Reading

- This audit parses pending live-call commands and checks local command/input/output surfaces only.
- It performs no live/API/model calls and writes no secret values.
- A ready command surface is not a live metric claim; credentials, quota, live outputs, output audit, scoring, and validation must still pass before promotion.
