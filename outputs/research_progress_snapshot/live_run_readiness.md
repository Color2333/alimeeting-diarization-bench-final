# Live Run Readiness

- Runtime contract: `live_run_readiness_non_secret_no_live_calls`
- Secret policy: `env_presence_only_no_secret_values_written`
- Ready runs: `0`
- Blocked runs: `3`
- P0 blocked: `1`
- Live calls performed: `0`
- DashScope/Bailian key present in env: `False`
- Config defaults counted as credentials: `False`

## Runs

| Run | Priority | Status | Calls | Windows | Models | Blockers | Input scale |
|---|---|---|---:|---:|---|---|---|
| `omni48_live` | `P1` | `blocked_missing_credentials` | 96 | 48 | qwen3.5-omni-flash<br>qwen3.5-omni-plus-2026-03-15 | missing_dashscope_or_bailian_api_key_env | 768.0 clip-model seconds proxy |
| `split20_deepseek_full` | `P0` | `blocked_by_provider_quota_or_capacity` | 139 | 101 | deepseek-v4-flash | missing_dashscope_or_bailian_api_key_env<br>known_deepseek_top4_5_failure_AllocationQuota.FreeTierOnly | 400862 prompt tokens proxy |
| `split20_qwen_backup` | `P1` | `blocked_missing_credentials` | 147 | 104 | qwen3.6-flash-2026-04-16 | missing_dashscope_or_bailian_api_key_env | 428566 prompt tokens proxy |

## Commands

### omni48_live

```bash
python scripts/llm/omni_guard_window_batch.py --input-windows-csv outputs/research_progress_snapshot/omni_expansion_manifest.csv --model qwen3.5-omni-flash --model qwen3.5-omni-plus-2026-03-15 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/omni_guard/omni_expansion_48_live.jsonl
```

### split20_deepseek_full

```bash
python scripts/llm/llm_window_batch_policy_eval.py --mode call --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --max-patches-per-call 20 --window-id-file outputs/research_progress_snapshot/split20_deepseek_resume_after_top3_window_ids.txt --model deepseek-v4-flash --parallel-workers 8 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl
```

### split20_qwen_backup

```bash
python scripts/llm/llm_window_batch_policy_eval.py --mode call --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --max-patches-per-call 20 --model qwen3.6-flash-2026-04-16 --parallel-workers 8 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl
```
