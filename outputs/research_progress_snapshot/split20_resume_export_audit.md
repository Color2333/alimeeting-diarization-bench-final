# Split20 Resume Export Audit

- Runtime contract: `split20_resume_export_audit_no_live_calls`
- Status: `pass`
- Export prompts: `139` / expected `139`
- Export parents: `101` / expected `101`
- Pending ids: `101`
- Completed overlap: `0`
- Failed quota parents retained: `2/2`
- Live calls performed: `0`
- Export prompt JSONL: `outputs/research_progress_snapshot/split20_resume_after_top3_export_prompts.jsonl`

## Command

```bash
/opt/homebrew/opt/python@3.11/bin/python3.11 scripts/llm_window_batch_policy_eval.py --mode export --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl --trigger-policy proxy_flagged_window --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt --window-id-file outputs/research_progress_snapshot/split20_deepseek_resume_after_top3_window_ids.txt --max-patches-per-call 20 --model deepseek-v4-flash --output-jsonl outputs/research_progress_snapshot/split20_resume_after_top3_export_prompts.jsonl
```

## Reading

- This audit runs the existing batch runner in export mode only; it does not call any model.
- It proves the resume window-id file selects the intended remaining parent windows after excluding completed top3.
- The two quota-failed top4/top5 windows remain in the pending surface, because they still need valid DeepSeek generation.
