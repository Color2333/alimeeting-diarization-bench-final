# Live Scoring Readiness

- Runtime contract: `live_scoring_readiness_no_live_calls`
- Status: `blocked_waiting_live_outputs`
- Scoring steps: `5`
- Ready to score: `0`
- Blocked steps: `5`
- P0 scoring steps: `2`
- Unique live output calls: `382`
- Expected input calls across scoring commands: `676`
- Live calls performed by builder: `0`
- Scoring commands executed: `False`

| Scoring step | Surface | Priority | Expected calls | Coverage gate | Status | Claim effect |
|---|---|---:|---:|---|---|---|
| `deepseek_resume_safety` | `deepseek_resume_after_top3` | `P0` | 139 | `blocked_missing_output` | `blocked_waiting_live_output` | enables full DeepSeek split20 safety half after resume output exists |
| `deepseek_full_split20_comparison` | `deepseek_resume_after_top3` | `P0` | 147 | `blocked_missing_output` | `blocked_waiting_live_output` | turns split20 from top3 smoke into full-surface latency evidence if successful |
| `qwen_full_backup_safety` | `qwen_full_backup` | `P1` | 147 | `blocked_missing_output` | `blocked_waiting_live_output` | keeps Qwen as execution fallback, not primary latency claim by default |
| `qwen_full_backup_comparison` | `qwen_full_backup` | `P1` | 147 | `blocked_missing_output` | `blocked_waiting_live_output` | documents full-surface backup behavior and latency if fallback run is executed |
| `omni48_label_summary` | `omni48_label_only` | `P1` | 96 | `blocked_missing_output` | `blocked_waiting_live_output` | enables Omni48 label-only recall/precision/latency scoring after live output exists |

## Commands

### deepseek_resume_safety

```bash
python scripts/analysis/analyze_runtime_safe_llm_guard.py --batch-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl --output-csv outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety.csv --output-md outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety.md --summary-json outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety_summary.json
```

- Success gate: harmful_accepts == 0; missing_patch_eval == 0; parent_window_decision_override true

### deepseek_full_split20_comparison

```bash
python scripts/analysis/summarize_split_llm_runs.py --split-csv outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel.csv --split-csv outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.csv --run-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_summary.json --run-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_summary.json --safety-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_split20_top3_parallel_safety_summary.json --safety-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3_safety_summary.json --output-json outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.json --output-md outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_full_live_comparison.md
```

- Success gate: parent_windows == 104; split_calls == 147; harmful_accepts == 0; report measured wall and token multiplier

### qwen_full_backup_safety

```bash
python scripts/analysis/analyze_runtime_safe_llm_guard.py --batch-jsonl outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl --output-csv outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_safety.csv --output-md outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_safety.md --summary-json outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_safety_summary.json
```

- Success gate: harmful_accepts == 0; fallback only unless latency beats primary or provider changes

### qwen_full_backup_comparison

```bash
python scripts/analysis/summarize_split_llm_runs.py --split-csv outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.csv --run-summary outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_summary.json --safety-summary outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_safety_summary.json --output-json outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_comparison.json --output-md outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live_comparison.md
```

- Success gate: parent_windows == 104; split_calls == 147; harmful_accepts == 0; compare against DeepSeek primary evidence

### omni48_label_summary

```bash
python scripts/analysis/summarize_omni_window_batch.py outputs/omni_guard/omni_expansion_48_live.csv --output-csv outputs/omni_guard/omni_expansion_48_live_summary.csv --output-md outputs/omni_guard/omni_expansion_48_live_summary.md
```

- Success gate: 96 calls complete; report high positive, clean false positive, avg/P95/max call latency; label-only no timeline writeback

## Reading

- This artifact plans post-live scoring only; it does not execute scoring commands or model calls.
- Output coverage must pass `live_output_audit` before a scoring command can support a claim.
- DeepSeek resume has P0 priority because it is the shortest path from split20 smoke to full-surface latency/safety evidence.
- Qwen remains a backup/fallback path unless full-surface latency evidence beats the primary route.
