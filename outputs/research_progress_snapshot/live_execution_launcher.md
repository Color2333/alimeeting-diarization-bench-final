# Live Execution Launcher

- Runtime contract: `live_execution_launcher_dry_run_no_live_calls`
- Secret policy: `env_presence_only_no_secret_values_written`
- Status: `dry_run_blocked_waiting_credentials_or_execute_flag`
- Live scope: `p0`
- Available live commands: `3`
- Selected live commands: `0`
- Available live calls: `382`
- Launcher selected calls: `0`
- P0 selected calls: `0`
- P1 selected calls: `0`
- Provider route status: `blocked_no_default_primary_provider`
- Provider route default scope: `none`
- Provider route blocks default: `True`
- Credential ready: `False`
- Execute live: `False`
- Execution blockers: `2`
- Executed live command rows: `0`
- Failed live command rows: `0`
- Started live command calls: `0`
- Passed live command calls: `0`
- Failed live command calls: `0`
- Postrun refresh executed: `False`
- Postrun refresh blocked by live failures: `False`
- Live calls performed by launcher: `0`
- Execute record exists: `False`
- Execute record path: `outputs/research_progress_snapshot/live_execution_launcher_execute_latest.json`
- Latest execute status: ``
- Latest execute started calls: `0`
- Latest execute passed calls: `0`
- Latest execute failed calls: `0`
- Latest execute postrun refresh executed: `False`
- No secret values written: `True`
- No new metric claim: `True`

| Step | Priority | Phase | Selected | Status | Calls | Command |
|---|---|---|---:|---|---:|---|
| `credential_preflight_refresh` | `P0` | `preflight` | `False` | `dry_run_preflight_not_executed` | 0 | `python scripts/build_live_run_readiness.py` |
| `live_deepseek_resume_primary` | `P0` | `live_call` | `False` | `blocked_by_provider_route` | 139 | `python scripts/llm_window_batch_policy_eval.py --mode call --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --window-id-file outputs/research_progress_snapshot/split20_deepseek_resume_after_top3_window_ids.txt --max-patches-per-call 20 --model deepseek-v4-flash --parallel-workers 8 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl` |
| `live_omni48_label_only_live` | `P1` | `live_call` | `False` | `dry_run_unselected` | 96 | `python scripts/omni_guard_window_batch.py --input-windows-csv outputs/research_progress_snapshot/omni_expansion_manifest.csv --model qwen3.5-omni-flash --model qwen3.5-omni-plus-2026-03-15 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/omni_guard/omni_expansion_48_live.jsonl` |
| `live_qwen_full_backup_optional` | `P1` | `fallback_live_call` | `False` | `dry_run_unselected` | 147 | `python scripts/llm_window_batch_policy_eval.py --mode call --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --max-patches-per-call 20 --model qwen3.6-flash-2026-04-16 --parallel-workers 8 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl` |
| `postrun_refresh_validation` | `P0` | `refresh_and_validate` | `True` | `dry_run_postrun_not_executed` | 0 | `python scripts/refresh_latest_research_artifacts.py` |

## Reading

- Default mode is dry-run and performs no live/API/model calls.
- Live execution requires `--execute-live` plus a DashScope/Bailian credential in the runner environment.
- Provider routing can block the old default P0/DeepSeek selection; explicit Qwen/Omni fallback scopes remain separate from primary latency claims.
- The launcher reuses the command surface audit rows, so command readiness, skip-existing output, retry limits, input paths, and secret-literal checks stay aligned with the runbook.
- Use an explicit scope only after the provider route decision and claim boundary are understood.
