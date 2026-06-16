# Post-Live Scoring Execution Plan

- Runtime contract: `post_live_scoring_execution_plan_no_live_calls`
- Status: `blocked_waiting_live_outputs`
- Scoring execution steps: `6`
- P0 / P1 execution steps: `3` / `3`
- Blocked execution steps: `6`
- Ready execution steps: `0`
- Scoring commands: `6`
- P0 scoring steps: `2`
- Readiness ready to score: `0`
- Missing output surfaces: `3`
- Expected live calls: `382`
- Metric contracts: `8`
- Schema contracts: `8`
- Scorecard rows: `9`
- Latency claim rows: `8`
- Ready to promote: `0`
- Traceability rows: `54`
- Live calls performed by builder: `0`
- No scoring commands executed: `True`
- No new metric claim: `True`

| # | Step | Priority | Surface | Phase | State | Promotion gate | Claim boundary |
|---:|---|---|---|---|---|---|---|
| 1 | `deepseek_resume_safety_score` | `P0` | `deepseek_resume_after_top3` | `safety_scoring` | `blocked_waiting_live_output` | `deepseek_split20_resume_safety` | `required_before_zero_harm_safety_claim` |
| 2 | `deepseek_full_split20_comparison_score` | `P0` | `deepseek_resume_after_top3` | `latency_comparison` | `blocked_waiting_live_output` | `deepseek_split20_resume_latency` | `required_before_full_surface_latency_claim` |
| 3 | `omni48_label_summary_score` | `P1` | `omni48_label_only` | `label_metric_scoring` | `blocked_waiting_live_output` | `omni48_label_metrics` | `label_only_no_timeline_writeback` |
| 4 | `qwen_full_backup_safety_score` | `P1` | `qwen_full_backup` | `fallback_safety_scoring` | `blocked_waiting_live_output` | `qwen_full_backup_claim` | `fallback_only_not_primary_claim` |
| 5 | `qwen_full_backup_comparison_score` | `P1` | `qwen_full_backup` | `fallback_latency_comparison` | `blocked_waiting_live_output` | `qwen_full_backup_claim` | `fallback_only_not_primary_latency_claim` |
| 6 | `promotion_refresh_validation` | `P0` | `report_ppt` | `promotion_and_refresh` | `blocked_waiting_scoring_outputs` | `report_ppt_traceability_after_promotion` | `required_before_report_ppt_claim_promotion` |

## Commands

### 1. deepseek_resume_safety_score

- Prerequisite gate: `deepseek resume JSONL exists with 139 successful rows and clean output audit`
- Success gate: `harmful_accepts == 0; missing_patch_eval == 0; parent_window_decision_override true`

```bash
python scripts/analysis/analyze_runtime_safe_llm_guard.py --batch-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl --output-csv outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety.csv --output-md outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety.md --summary-json outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety_summary.json
```

### 2. deepseek_full_split20_comparison_score

- Prerequisite gate: `deepseek resume safety summary exists and harmful_accepts == 0`
- Success gate: `parent_windows == 104; split_calls == 147; harmful_accepts == 0; report measured wall and token multiplier`

```bash
python scripts/analysis/summarize_split_llm_runs.py --split-csv outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel.csv --split-csv outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.csv --run-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_summary.json --run-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_summary.json --safety-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_safety_summary.json --safety-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety_summary.json --output-json outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.json --output-md outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.md
```

### 3. omni48_label_summary_score

- Prerequisite gate: `Omni48 live CSV/JSONL exists with 96 complete label-only calls`
- Success gate: `96 calls complete; report high positive, clean false positive, avg/P95/max call latency; label-only no timeline writeback`

```bash
python scripts/analysis/summarize_omni_window_batch.py outputs/omni_guard/omni_expansion_48_live.csv --output-csv outputs/omni_guard/omni_expansion_48_live_summary.csv --output-md outputs/omni_guard/omni_expansion_48_live_summary.md
```

### 4. qwen_full_backup_safety_score

- Prerequisite gate: `Qwen full backup JSONL exists with 147 successful rows and clean output audit`
- Success gate: `harmful_accepts == 0; fallback only unless latency beats primary or provider changes`

```bash
python scripts/analysis/analyze_runtime_safe_llm_guard.py --batch-jsonl outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl --output-csv outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_safety.csv --output-md outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_safety.md --summary-json outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_safety_summary.json
```

### 5. qwen_full_backup_comparison_score

- Prerequisite gate: `Qwen backup safety summary exists and fallback comparison is explicitly requested`
- Success gate: `parent_windows == 104; split_calls == 147; harmful_accepts == 0; compare against DeepSeek primary evidence`

```bash
python scripts/analysis/summarize_split_llm_runs.py --split-csv outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.csv --run-summary outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_summary.json --safety-summary outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_safety_summary.json --output-json outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_comparison.json --output-md outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_comparison.md
```

### 6. promotion_refresh_validation

- Prerequisite gate: `required P0 scoring outputs exist and promotion gates remain traceable`
- Success gate: `refresh pass; validator failed_checks empty; traceability fully covered`

```bash
python scripts/misc/refresh_latest_research_artifacts.py
```

## Reading

- This plan orders post-live scoring commands after live output audit has clean complete outputs.
- DeepSeek P0 safety must pass before the full split20 comparison can support latency promotion.
- Omni48 remains label-only and Qwen remains fallback-only unless a later promotion gate changes those claim boundaries.
- The builder performs no live/API/model/scoring calls and writes no secret values.
