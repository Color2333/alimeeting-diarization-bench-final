# Split20 Full Live Manifest

- Runtime contract: `split20_full_live_manifest_no_live_calls`
- Parent windows: `104`
- Prompt calls: `147`
- Patch references: `1917`
- Split parent windows: `40`
- Max subcalls per parent: `3`
- Estimated prompt tokens proxy: `428566`
- Simulated P95 call: `21.358s`
- Simulated P95 correction delay: `46.005s`
- DeepSeek completed: `3` parents / `8` calls
- DeepSeek top3 wall: `29.014s`; harmful accepts `0`
- DeepSeek quota failed: `2` parents / `4` calls; `AllocationQuota.FreeTierOnly`
- DeepSeek resume surface: `101` parents / `139` calls
- Qwen backup: `2` parents / `4` calls; wall `44.024s`; harmful `0`
- Live calls performed by builder: `0`

## Resume Surface

- Pending window-id file: `outputs/research_progress_snapshot/split20_deepseek_resume_after_top3_window_ids.txt`
- Pending parent windows: `101`
- Pending calls: `139`
- Completed top3 window-id file: `outputs/research_progress_snapshot/split20_deepseek_completed_top3_window_ids.txt`
- Failed quota window-id file: `outputs/research_progress_snapshot/split20_deepseek_quota_failed_window_ids.txt`

## Commands

### deepseek_full_parallel

```bash
python scripts/llm/llm_window_batch_policy_eval.py --mode call --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --max-patches-per-call 20 --model deepseek-v4-flash --parallel-workers 8 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_live.jsonl
```

### deepseek_resume_after_top3

```bash
python scripts/llm/llm_window_batch_policy_eval.py --mode call --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --window-id-file outputs/research_progress_snapshot/split20_deepseek_resume_after_top3_window_ids.txt --max-patches-per-call 20 --model deepseek-v4-flash --parallel-workers 8 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl
```

### qwen_backup_full_parallel

```bash
python scripts/llm/llm_window_batch_policy_eval.py --mode call --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --max-patches-per-call 20 --model qwen3.6-flash-2026-04-16 --parallel-workers 8 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/runtime_safe_llm_window_batch/qwen36_flash_high_risk_104w_split20_live.jsonl
```

## Slowest Parent Windows

| Parent | Patches | Subcalls | Original call | Sim split | DeepSeek status | Qwen status |
|---|---:|---:|---:|---:|---|---|
| R8007_M8010:30:0 | 45 | 3 | 48.47s | 18.05s | `completed_top3_parallel` | `not_run` |
| R8007_M8010:30:6 | 40 | 2 | 44.56s | 23.47s | `completed_top3_parallel` | `not_run` |
| R8007_M8010:30:3 | 42 | 3 | 39.72s | 17.22s | `completed_top3_parallel` | `not_run` |
| R8009_M8020:30:12 | 37 | 2 | 36.45s | 21.95s | `failed_AllocationQuota.FreeTierOnly` | `completed_backup` |
| R8003_M8001:30:12 | 23 | 2 | 35.73s | 16.87s | `failed_AllocationQuota.FreeTierOnly` | `completed_backup` |
| R8003_M8001:30:2 | 30 | 2 | 35.52s | 18.04s | `pending_live` | `not_run` |
| R8007_M8010:30:2 | 32 | 2 | 34.40s | 18.58s | `pending_live` | `not_run` |
| R8003_M8001:30:10 | 33 | 2 | 32.75s | 19.45s | `pending_live` | `not_run` |
| R8007_M8010:30:12 | 33 | 2 | 32.25s | 19.53s | `pending_live` | `not_run` |
| R8001_M8004:30:10 | 35 | 2 | 29.93s | 20.45s | `pending_live` | `not_run` |
| R8003_M8001:30:5 | 27 | 2 | 29.74s | 17.20s | `pending_live` | `not_run` |
| R8001_M8004:30:1 | 16 | 1 | 29.35s | 20.70s | `pending_live` | `not_run` |

## Reading

- This manifest is the execution surface for the P0 full split20 live validation; it does not call any model.
- The current positive latency evidence is limited to the DeepSeek top3 parallel smoke.
- Qwen backup proves the top4/top5 execution path can run with harmful accept 0, but it is slower and cannot support the latency claim.
- Full-surface latency remains unclaimed until the DeepSeek quota/capacity blocker is removed and all 104 parent windows complete.
