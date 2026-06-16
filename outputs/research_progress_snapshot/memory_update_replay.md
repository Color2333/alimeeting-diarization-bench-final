# Memory Update Replay

- Runtime contract: `memory_update_replay_review_signal_blocks_memory_only`
- Review cases: `4`
- Memory candidates before: `4`
- Memory updates allowed after: `0`
- Memory updates blocked: `4`
- Timeline writebacks preserved: `4`
- Failed rows: `0`

## Cases

| Patch ID | Case | LLM action | Memory before | Memory after | Block reasons | Timeline preserved | LLM arrival |
|---|---|---|---:|---:|---|---:|---:|
| `R8009_M8018:30:2:fast:fast_8` | repeatability_drift | review_repeatability_drift | 1 | 0 | repeatability_drift_review_signal, duration_under_1s | 1 | 43.48s |
| `R8009_M8018:30:2:fast:fast_9` | repeatability_drift | review_repeatability_drift | 1 | 0 | repeatability_drift_review_signal, duration_under_1s | 1 | 43.48s |
| `R8009_M8018:30:3:fast:fast_8` | full_defer | review_llm_defer | 1 | 0 | duration_under_1s, llm_memory_constraint | 1 | 55.80s |
| `R8009_M8020:30:14:fast:fast_1` | full_defer | review_llm_defer | 1 | 0 | support_under_0.85, margin_under_0.50, llm_memory_constraint | 1 | 41.63s |

## Reading

- Review/defer/repeatability signals are converted into memory-update blocks.
- Rule timeline writeback is preserved for all replayed cases.
- The replay surface avoids DER/GT/oracle/eval-only fields.
