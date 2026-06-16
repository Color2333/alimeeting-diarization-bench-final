# Split15 Stretch Re-export Audit

- Runtime contract: `split15_stretch_reexport_audit_no_live_calls`
- Status: `pass`
- Export prompts: `178` / expected `178`
- Export parents: `104` / expected `104`
- Split parent windows: `58` / expected `58`
- Max subcalls per parent: `3`
- Simulated P95 call: `18.047`
- Token multiplier: `1.182`
- Top3 live evidence reusable: `False`
- Requires new prompt export: `True`
- Live calls performed: `0`
- No new metric claim: `True`
- Export prompt JSONL: `outputs/research_progress_snapshot/split15_stretch_reexport_prompts.jsonl`

## Command

```bash
/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/llm_window_batch_policy_eval.py --mode export --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --max-patches-per-call 15 --model deepseek-v4-flash --output-jsonl outputs/research_progress_snapshot/split15_stretch_reexport_prompts.jsonl
```

## Reading

- This audit runs the existing batch runner in export mode only; it does not call any model.
- The max15 surface is a stretch latency candidate, not the default P0 live path.
- It cannot reuse max20 top3 live evidence as full-surface evidence; a fresh live output and scoring pass are required before any claim promotion.
