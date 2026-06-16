# Live Agent Execution Plan

- Runtime contract: `live_agent_execution_plan_no_live_calls`
- Status: `pass`
- Steps: `5`
- Live steps: `3`
- Blocked steps: `5`
- Planned live calls: `382`
- P0 planned live calls: `139`
- DeepSeek resume calls: `139`
- Omni label-only calls: `96`
- Live calls performed: `0`
- No secret values written: `True`

## Steps

| Step | Priority | Status | Calls | Windows | Est. wall | Latency metric | Writeback |
|---|---|---|---:|---:|---:|---|---|
| `credential_preflight` | `P0` | `blocked_missing_credentials` | 0 | 0 | 0.000s | `gate_only` | `none` |
| `split20_deepseek_resume_after_top3` | `P0` | `blocked_by_provider_quota_or_capacity` | 139 | 101 | 384.444s | `resume_budget_from_split20_simulated_p95` | `block_or_quarantine_only` |
| `split20_qwen_backup_full_surface` | `P1` | `blocked_missing_credentials` | 147 | 104 | 836.456s | `backup_path_budget_not_latency_supporting` | `block_or_quarantine_only` |
| `omni48_label_only_live` | `P1` | `blocked_missing_credentials` | 96 | 48 | n/a | `needs_live_first_text_and_total_latency_measurement` | `label_only_no_timeline_writeback` |
| `postrun_refresh_and_validation` | `P0` | `waiting_for_live_outputs` | 0 | 0 | n/a | `validation_only` | `none` |

## Commands

### credential_preflight

- Blockers: `missing_dashscope_or_bailian_api_key_env`
- Postrun artifacts: `outputs/research_progress_snapshot/live_run_readiness.json`

```bash
export DASHSCOPE_API_KEY=...  # or BAILIAN_API_KEY / ALIYUN_BAILIAN_API_KEY; do not write secrets to artifacts
```

### split20_deepseek_resume_after_top3

- Blockers: `missing_dashscope_or_bailian_api_key_env; known_deepseek_top4_5_failure_AllocationQuota.FreeTierOnly`
- Postrun artifacts: `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl; outputs/research_progress_snapshot/split20_full_live_manifest.json; outputs/research_progress_snapshot/latest_artifact_validation.md`

```bash
python scripts/llm_window_batch_policy_eval.py --mode call --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --window-id-file outputs/research_progress_snapshot/split20_deepseek_resume_after_top3_window_ids.txt --max-patches-per-call 20 --model deepseek-v4-flash --parallel-workers 8 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl
```

### split20_qwen_backup_full_surface

- Blockers: `missing_dashscope_or_bailian_api_key_env`
- Postrun artifacts: `outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl; outputs/research_progress_snapshot/latest_artifact_validation.md`

```bash
python scripts/llm_window_batch_policy_eval.py --mode call --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --max-patches-per-call 20 --model qwen3.6-flash-2026-04-16 --parallel-workers 8 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl
```

### omni48_label_only_live

- Blockers: `missing_dashscope_or_bailian_api_key_env`
- Postrun artifacts: `outputs/omni_guard/omni_expansion_48_live.jsonl; outputs/research_progress_snapshot/latest_artifact_validation.md`

```bash
python scripts/omni_guard_window_batch.py --input-windows-csv outputs/research_progress_snapshot/omni_expansion_manifest.csv --model qwen3.5-omni-flash --model qwen3.5-omni-plus-2026-03-15 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/omni_guard/omni_expansion_48_live.jsonl
```

### postrun_refresh_and_validation

- Blockers: `requires_completed_live_outputs`
- Postrun artifacts: `outputs/research_progress_snapshot/refresh_latest_artifacts.md; outputs/research_progress_snapshot/latest_artifact_validation.md; ../研究进展汇报.pptx`

```bash
python scripts/refresh_latest_research_artifacts.py
```

## Reading

- This plan is an Agent handoff manifest; it performs no live model/API calls.
- DeepSeek resume is the P0 path for finishing the split20 latency claim after the completed top3 smoke.
- Qwen backup is kept as an execution fallback, but current evidence says it is not latency-supporting.
- Omni48 remains label-only and has no timeline writeback right; first text and total latency still require a live run.
