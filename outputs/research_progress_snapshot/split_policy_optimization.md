# Split Policy Optimization

- Runtime contract: `split_policy_optimization_from_existing_artifacts_no_live_calls`
- Status: `ready_primary_resume_blocked_by_live_outputs_or_quota`
- Policies: `5`
- Primary policy: `max20`
- Primary calls / resume calls: `147` / `139`
- Primary simulated P95 call: `21.358`
- Primary token multiplier: `1.118`
- Stretch policy: `max15`
- Stretch simulated P95 call: `18.047`
- Stretch requires re-export: `True`
- Live calls performed by builder: `0`
- No metric claim: `True`

| Max patches | Role | Calls | Resume calls | Added calls | Split windows | P95 call | Max call | Token multiplier | Top3 reusable | Quota risk |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 20 | `resume_primary` | 147 | 139 | 43 | 40 | 21.358 | 23.468 | 1.118 | `True` | `lowest` |
| 15 | `latency_stretch_reexport` | 178 | 178 | 74 | 58 | 18.047 | 19.646 | 1.182 | `False` | `medium` |
| 12 | `exploratory_low_latency_high_cost` | 209 | 209 | 105 | 70 | 16.19 | 17.149 | 1.246 | `False` | `high` |
| 10 | `exploratory_low_latency_high_cost` | 239 | 239 | 135 | 76 | 15.081 | 16.227 | 1.307 | `False` | `high` |
| 8 | `exploratory_low_latency_high_cost` | 286 | 286 | 182 | 82 | 13.647 | 14.252 | 1.404 | `False` | `high` |

## Reading

- `max20` remains the primary live path because it has exported prompts, completed top3 live smoke, and a clean resume surface.
- `max15` is the next latency-stretch candidate: lower simulated P95, but it needs a fresh export and cannot directly reuse the max20 top3 smoke as full-surface evidence.
- Smaller max-patch policies reduce simulated P95 further but raise call count and quota pressure; keep them exploratory until provider capacity is stable.
- This artifact is an offline planning layer and makes no live metric claim.

## Commands

```bash
python scripts/llm/llm_window_batch_policy_eval.py --mode call --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --window-id-file outputs/research_progress_snapshot/split20_deepseek_resume_after_top3_window_ids.txt --max-patches-per-call 20 --model deepseek-v4-flash --parallel-workers 8 --skip-existing-output --max-call-attempts 2 --retry-backoff-seconds 2.0 --output-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_resume_after_top3.jsonl
```

```bash
python scripts/llm/llm_window_batch_policy_eval.py --mode export --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --max-patches-per-call 15 --output-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split15_replay_prompts.jsonl
```
