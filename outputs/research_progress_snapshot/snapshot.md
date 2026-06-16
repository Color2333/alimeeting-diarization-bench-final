# Research Progress Snapshot

| Area | Current evidence |
|---|---|
| Four-stage timeline | 0.38s first output; 24.65s rule writeback; 44.92s LLM guard; 46.10s LLM review |
| Runtime evidence audit | pass; 16 artifacts; blocking 0 |
| Rule writeback | 599 patches; recovers 60.2% Fast miss; 197.36s unique miss recovered |
| Selector generalization | holdout 8/8 positive; DER 26.5% vs Fast 28.6%; delta 2.1%; fixed ratio_le_0.65_else_uncovered 26.3%; bootstrap delta 2.2% (1.1% - 3.5%) |
| Runtime-safe LLM guard | 104 windows / 1917 patches; harmful accept 0; delay 44.92s / P95 63.85s |
| Split20 LLM guard optimization | 147 prompts / 104 parent windows; top3 live wall 29.01s vs original max 48.47s; split max 28.99s; harmful 0; qwen backup wall 44.02s slower; deepseek top4/5 AllocationQuota.FreeTierOnly |
| Guard tuning contract | combined_review0.5_keepfast0.5 recovers 260 conservative blocks; materialized safe 323 / harmful 0; boundary auto-writeback DER 33.8% vs recover-best 26.4% |
| Clean high LLM audit | 136/138 accept; 2 non-accept; agreement 98.6% |
| Timeline review audit | 4 review cases; blocks writeback 0; blocks memory 4; arrival 46.10s |
| Omni fusion | 12 windows; high sentinel recall 1/4 (25.0%); clean sentinel FP 0/4 (0.0%); review FP 4/4 (100.0%) |
| Voiceprint gate | 620/620 clean patches with voiceprint; high 226; high rule-auto 138; LLM candidates 0 |

## Reading

- Current deployable route is staged: Fast output first, Rule writes bounded corrections, LLM/Omni only guard or review.
- Selector gain is development-set evidence, but recording holdout and bootstrap checks reduce concentration-risk concerns.
- Split20 is the current latency optimization path for LLM guard: top3 live parallel smoke is faster, but full 104-window rerun is still not proven.
- Guard tuning can reduce conservative blocking under a review/passthrough contract, but boundary auto-writeback remains a negative control.
- Clean high voiceprint patches are already handled by deterministic Rule writeback; LLM remains an audit/explanation layer.
- Review signals block memory update, not timeline writeback.
