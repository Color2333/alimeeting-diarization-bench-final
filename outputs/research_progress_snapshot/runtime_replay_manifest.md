# Runtime Replay Manifest

- Runtime contract: `end_to_end_runtime_replay_manifest_no_eval_context`
- Stages: `6`
- Runtime-audit pass rows: `5`
- Claim-manifest-only rows: `1`
- Failed rows: `0`
- Timeline writeback rows: `fast_provisional, rule_writeback`

| Stage | Agent | Arrival avg | Arrival P95 | Writeback right | Runtime action | Runtime audit | Sources | Validation |
|---|---|---:|---:|---|---|---|---|---|
| `fast_provisional` | Fast Agent / Sortformer | 0.38s | 0.44s | `timeline_first_output` | emit provisional speaker timeline | `pass` / `pass` | `outputs/system_timeline/system_timeline.csv`<br>`outputs/system_timeline/summary.json` | `four_stage_timeline`, `runtime_audit_pass` |
| `rule_writeback` | Slow Acoustic + Rule Agent | 24.65s | 28.33s | `bounded_timeline_writeback` | write bounded corrections from 599 candidate patches | `pass` / `pass` | `outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.csv`<br>`outputs/system_timeline/system_timeline.csv` | `runtime_audit_pass`, `four_stage_timeline` |
| `llm_guard` | LLM Guard / deepseek-v4-flash | 44.92s | 63.85s | `block_or_quarantine_only` | guard 104 proxy windows / 1917 patches; harmful accept 0 | `pass` / `pass` | `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_prompts.jsonl`<br>`outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_safety_summary.json` | `runtime_audit_pass`, `split20_live_top3_guard` |
| `llm_review_signal` | LLM Review / qwen3.6-flash audit | 46.10s | 55.80s | `memory_protection_only` | 4 review cases; timeline writeback blocks 0; memory blocks 4 | `pass` / `pass` | `outputs/timeline_review_audit/llm_review_signal_timeline_audit.csv`<br>`outputs/timeline_review_audit/llm_review_signal_timeline_audit_summary.json` | `review_signal_no_timeline_block`, `pareto_has_review_signal` |
| `omni_label` | Omni Realtime Risk Probe | 2.11s | 6.41s | `label_and_quarantine_priority_only` | 12 windows; high sentinel recall 1/4 (25.0%); clean review FP 4/4 (100.0%) | `pass` / `pass` | `outputs/omni_guard/omni_acoustic_fusion.csv`<br>`outputs/omni_guard/omni_acoustic_fusion_summary.json` | `omni_fusion_label_only_contract`, `runtime_audit_pass` |
| `memory_gate` | Speaker Memory Gate | non_blocking | non_blocking | `speaker_memory_update_after_gate` | 620/620 clean patches have voiceprint evidence; LLM candidates 0 | `claim_manifest_only` / `pass` | `outputs/voiceprint_patch_evidence/clean_candidate_120_summary.json`<br>`outputs/voiceprint_patch_evidence/clean_candidate_120_voiceprint.csv` | `claims_manifest_contract`, `snapshot_contract` |
