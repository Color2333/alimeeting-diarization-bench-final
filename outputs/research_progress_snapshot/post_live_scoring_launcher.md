# Post-Live Scoring Launcher

- Runtime contract: `post_live_scoring_launcher_dry_run_no_scoring_calls`
- Secret policy: `commands_scanned_no_secret_values_written`
- Status: `dry_run_blocked_waiting_live_outputs_or_execute_flag`
- Scoring scope: `p0`
- Available scoring rows: `6`
- Ready scoring rows: `0`
- Selected scoring rows: `0`
- Execute scoring: `False`
- Execution blockers: `2`
- Executed scoring rows: `0`
- Passed scoring rows: `0`
- Failed scoring rows: `0`
- Output missing surfaces: `3`
- Repair scoring-ready rows: `0`
- Traceability rows: `54`
- Scoring execute record exists: `False`
- Scoring execute record path: `outputs/research_progress_snapshot/post_live_scoring_launcher_execute_latest.json`
- Latest scoring execute status: ``
- Latest scoring executed rows: `0`
- Latest scoring passed rows: `0`
- Latest scoring failed rows: `0`
- No live calls performed: `True`
- No scoring commands executed: `True`
- No new metric claim: `True`

| Step | Priority | Surface | Eligible | Selected | Status | Promotion gate |
|---|---|---|---:|---:|---|---|
| `deepseek_resume_safety_score` | `P0` | `deepseek_resume_after_top3` | `False` | `False` | `blocked_waiting_prerequisite` | `deepseek_split20_resume_safety` |
| `deepseek_full_split20_comparison_score` | `P0` | `deepseek_resume_after_top3` | `False` | `False` | `blocked_waiting_prerequisite` | `deepseek_split20_resume_latency` |
| `omni48_label_summary_score` | `P1` | `omni48_label_only` | `False` | `False` | `blocked_waiting_prerequisite` | `omni48_label_metrics` |
| `qwen_full_backup_safety_score` | `P1` | `qwen_full_backup` | `False` | `False` | `blocked_waiting_prerequisite` | `qwen_full_backup_claim` |
| `qwen_full_backup_comparison_score` | `P1` | `qwen_full_backup` | `False` | `False` | `blocked_waiting_prerequisite` | `qwen_full_backup_claim` |
| `promotion_refresh_validation` | `P0` | `report_ppt` | `False` | `False` | `blocked_waiting_prerequisite` | `report_ppt_traceability_after_promotion` |

## Reading

- Default mode is dry-run and executes no scoring command.
- `--execute-scoring` only runs rows whose current state is ready in the scoring execution plan.
- Current blocked rows stay blocked until live output audit, repair plan, and scoring readiness agree that outputs are complete.
- The launcher performs no live/API/model calls and writes no secret values.
