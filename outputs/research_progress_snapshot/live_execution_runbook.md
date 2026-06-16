# Live Execution Runbook

- Runtime contract: `live_execution_runbook_no_live_calls_no_secret_values`
- Secret policy: `env_presence_only_no_secret_values_written`
- Status: `blocked_waiting_for_credentials_or_live_outputs`
- Steps: `7`
- P0 / P1 steps: `5` / `2`
- Blocked steps: `5`
- Planned live calls total: `382`
- P0 planned live calls: `139`
- DeepSeek primary policy: `max20`
- Claim-now SLO pass: `4/4`
- Live calls performed by builder: `0`
- No secret values written: `True`

| # | Step | Priority | Phase | Status | Calls | Writeback | Success gate |
|---:|---|---|---|---|---:|---|---|
| 1 | `credential_preflight` | `P0` | `preflight` | `blocked_missing_credentials` | 0 | `none` | live_run_readiness reports credential env presence true; no secret values written |
| 2 | `deepseek_resume_primary` | `P0` | `live_call` | `blocked_by_provider_quota_or_capacity` | 139 | `block_or_quarantine_only` | 139 successful calls / 101 parent windows; no provider quota failures |
| 3 | `post_live_output_audit` | `P0` | `postrun_audit` | `pending_live_outputs` | 0 | `none` | deepseek_resume_after_top3 claim_gate is ready_for_llm_safety_latency_scoring |
| 4 | `deepseek_resume_safety_and_comparison` | `P0` | `postrun_scoring` | `blocked_waiting_live_output` | 0 | `none` | harmful_accepts == 0 and parent_windows == 104 and split_calls == 147 |
| 5 | `omni48_label_only_live` | `P1` | `live_call` | `blocked_missing_credentials` | 96 | `label_only_no_timeline_writeback` | 96 successful label-only calls; no timeline writeback |
| 6 | `qwen_full_backup_optional` | `P1` | `fallback_live_call` | `blocked_missing_credentials` | 147 | `block_or_quarantine_only` | fallback safety harmful_accepts == 0; do not promote as primary latency unless faster |
| 7 | `refresh_report_ppt_validation` | `P0` | `refresh_and_validate` | `waiting_for_live_outputs` | 0 | `none` | refresh pass and validation failed_checks == [] |

## Commands

### 1. credential_preflight

- Blocking gate: `dashscope_or_bailian_api_key_env_present`
- Expected artifacts: `outputs/research_progress_snapshot/live_run_readiness.json`

```bash
export DASHSCOPE_API_KEY=...  # or BAILIAN_API_KEY / ALIYUN_BAILIAN_API_KEY; keep secrets out of artifacts
```

### 2. deepseek_resume_primary

- Blocking gate: `missing_dashscope_or_bailian_api_key_env;known_deepseek_top4_5_failure_AllocationQuota.FreeTierOnly`
- Expected artifacts: `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl`

```bash
python scripts/llm_window_batch_policy_eval.py --mode call --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --window-id-file outputs/research_progress_snapshot/split20_deepseek_resume_after_top3_window_ids.txt --max-patches-per-call 20 --model deepseek-v4-flash --parallel-workers 8 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl
```

### 3. post_live_output_audit

- Blocking gate: `live output JSONL must exist before claim-ready`
- Expected artifacts: `outputs/research_progress_snapshot/live_output_audit.json`

```bash
python scripts/build_live_output_audit.py
```

### 4. deepseek_resume_safety_and_comparison

- Blocking gate: `blocked_missing_output`
- Expected artifacts: `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety.csv;outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety.md;outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety_summary.json;outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.json;outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.md`

```bash
python scripts/analyze_runtime_safe_llm_guard.py --batch-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl --output-csv outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety.csv --output-md outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety.md --summary-json outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety_summary.json && python scripts/summarize_split_llm_runs.py --split-csv outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel.csv --split-csv outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.csv --run-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_summary.json --run-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_summary.json --safety-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_safety_summary.json --safety-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety_summary.json --output-json outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.json --output-md outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.md
```

### 5. omni48_label_only_live

- Blocking gate: `missing_dashscope_or_bailian_api_key_env`
- Expected artifacts: `outputs/omni_guard/omni_expansion_48_live.jsonl`

```bash
python scripts/omni_guard_window_batch.py --input-windows-csv outputs/research_progress_snapshot/omni_expansion_manifest.csv --model qwen3.5-omni-flash --model qwen3.5-omni-plus-2026-03-15 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/omni_guard/omni_expansion_48_live.jsonl
```

### 6. qwen_full_backup_optional

- Blocking gate: `missing_dashscope_or_bailian_api_key_env`
- Expected artifacts: `outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl`

```bash
python scripts/llm_window_batch_policy_eval.py --mode call --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --max-patches-per-call 20 --model qwen3.6-flash-2026-04-16 --parallel-workers 8 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl
```

### 7. refresh_report_ppt_validation

- Blocking gate: `requires_completed_live_outputs`
- Expected artifacts: `outputs/research_progress_snapshot/latest_artifact_validation.md; ../研究进展汇报.pptx; docs/reports/2026-06-03-realtime-dual-agent-roadmap.md`

```bash
python scripts/refresh_latest_research_artifacts.py
```

## Reading

- This runbook is a live-execution handoff artifact; it performs no model/API calls.
- Credentials are represented only as environment-presence gates; no secret values are written.
- P0 execution remains DeepSeek max20 resume first, followed by output audit, safety scoring, comparison, and refresh validation.
- Omni48 and Qwen full backup remain P1 unless the user explicitly chooses to spend provider quota there.
