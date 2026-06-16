# Live Execution Bundle

- Runtime contract: `live_execution_bundle_no_live_calls_no_secret_values`
- Secret policy: `env_presence_only_no_secret_values_written`
- Status: `blocked_waiting_credentials_quota_or_live_outputs`
- Bundle steps: `8`
- P0 / P1 steps: `6` / `2`
- Blocked/waiting steps: `8`
- Live-call steps: `3`
- Command-ready: `3/3`
- Planned live calls: `382`
- P0 planned live calls: `139`
- Credential ready: `False`
- Known provider quota blockers: `1`
- Missing output surfaces: `3`
- DAG nodes: `10`
- DeepSeek estimated wall seconds: `384.444`
- Max attempted requests: `764`
- LLM retry token proxy ceiling: `1658856`
- Traceability rows: `54`
- Live calls performed by builder: `0`
- No scoring commands executed: `True`
- No new metric claim: `True`

| # | Step | Priority | Phase | State | Calls | DAG node | Boundary |
|---:|---|---|---|---|---:|---|---|
| 1 | `credential_preflight` | `P0` | `preflight` | `blocked_missing_credentials` | 0 | `live_outputs_complete` | `no_secret_values_no_live_calls` |
| 2 | `p0_deepseek_resume_live` | `P0` | `live_call` | `blocked_by_provider_quota_or_capacity` | 139 | `live_outputs_complete` | `block_or_quarantine_only_until_safety_scored` |
| 3 | `p0_output_audit` | `P0` | `postrun_audit` | `pending_live_outputs` | 0 | `output_schema_clean` | `output_audit_no_metric_claim` |
| 4 | `p0_safety_then_latency_scoring` | `P0` | `postrun_scoring` | `blocked_waiting_live_output` | 0 | `deepseek_resume_safety_score` | `required_before_zero_harm_and_full_surface_latency_claim` |
| 5 | `p0_metrics_promotion_refresh` | `P0` | `promotion_refresh` | `blocked_waiting_scoring_outputs` | 0 | `promotion_gate_pass` | `report_ppt_sync_required_before_claim_promotion` |
| 6 | `p1_omni48_label_live` | `P1` | `live_call` | `blocked_missing_credentials` | 96 | `omni48_label_metrics` | `label_only_no_timeline_writeback` |
| 7 | `p1_qwen_backup_live` | `P1` | `fallback_live_call` | `blocked_missing_credentials` | 147 | `qwen_backup_metrics` | `fallback_only_not_primary_claim` |
| 8 | `final_report_ppt_validation` | `P0` | `refresh_and_validate` | `waiting_for_live_outputs` | 0 | `report_ppt_refresh_validation` | `final_validation_no_new_metric_claim` |

## Commands

### 1. credential_preflight

- Depends on: `root`
- Expected artifacts: `outputs/research_progress_snapshot/live_run_readiness.json`
- Success gate: `credential env presence true; no secret values written`

```bash
python scripts/build_live_run_readiness.py
```

### 2. p0_deepseek_resume_live

- Depends on: `credential_preflight`
- Expected artifacts: `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl`
- Success gate: `139 successful calls / 101 parent windows; no provider quota failures`

```bash
python scripts/llm_window_batch_policy_eval.py --mode call --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --window-id-file outputs/research_progress_snapshot/split20_deepseek_resume_after_top3_window_ids.txt --max-patches-per-call 20 --model deepseek-v4-flash --parallel-workers 8 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl
```

### 3. p0_output_audit

- Depends on: `p0_deepseek_resume_live`
- Expected artifacts: `outputs/research_progress_snapshot/live_output_audit.json`
- Success gate: `missing_output_surfaces == 0 for P0 surface before scoring`

```bash
python scripts/build_live_output_audit.py
```

### 4. p0_safety_then_latency_scoring

- Depends on: `p0_output_audit`
- Expected artifacts: `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety_summary.json; outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.json`
- Success gate: `harmful_accepts == 0 before full split20 latency comparison can promote`

```bash
python scripts/analyze_runtime_safe_llm_guard.py --batch-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl --output-csv outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety.csv --output-md outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety.md --summary-json outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety_summary.json
python scripts/summarize_split_llm_runs.py --split-csv outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel.csv --split-csv outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.csv --run-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_summary.json --run-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_summary.json --safety-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_safety_summary.json --safety-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety_summary.json --output-json outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.json --output-md outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.md
```

### 5. p0_metrics_promotion_refresh

- Depends on: `p0_safety_then_latency_scoring`
- Expected artifacts: `outputs/research_progress_snapshot/post_live_claim_promotion_gate.json; outputs/research_progress_snapshot/latest_artifact_validation.json; ../研究进展汇报.pptx`
- Success gate: `refresh pass; validator failed_checks empty; traceability fully covered`

```bash
python scripts/refresh_latest_research_artifacts.py
```

### 6. p1_omni48_label_live

- Depends on: `credential_preflight`
- Expected artifacts: `outputs/omni_guard/omni_expansion_48_live.jsonl`
- Success gate: `96 successful label-only calls; no timeline writeback`

```bash
python scripts/omni_guard_window_batch.py --input-windows-csv outputs/research_progress_snapshot/omni_expansion_manifest.csv --model qwen3.5-omni-flash --model qwen3.5-omni-plus-2026-03-15 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/omni_guard/omni_expansion_48_live.jsonl
```

### 7. p1_qwen_backup_live

- Depends on: `credential_preflight`
- Expected artifacts: `outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl`
- Success gate: `fallback safety harmful_accepts == 0; do not promote as primary latency unless policy changes`

```bash
python scripts/llm_window_batch_policy_eval.py --mode call --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --max-patches-per-call 20 --model qwen3.6-flash-2026-04-16 --parallel-workers 8 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl
```

### 8. final_report_ppt_validation

- Depends on: `p0_metrics_promotion_refresh`
- Expected artifacts: `outputs/research_progress_snapshot/refresh_latest_artifacts.json; outputs/research_progress_snapshot/latest_artifact_validation.json; outputs/research_progress_snapshot/report_ppt_traceability.json`
- Success gate: `refresh pass; latest validation failed_checks == []`

```bash
python scripts/refresh_latest_research_artifacts.py
```

## Reading

- This bundle is the ordered handoff between readiness/runbook artifacts and the post-live evidence DAG.
- It keeps P0 DeepSeek resume, output audit, safety, latency comparison, promotion, and report/PPT validation in one executable sequence.
- Omni48 remains label-only and Qwen remains fallback-only; neither can promote timeline writeback or primary latency claims from this bundle alone.
- The builder performs no live/API/model/scoring calls, writes no secret values, and makes no new metric claim.
