# Live Failure Recovery Playbook

- Runtime contract: `live_failure_recovery_playbook_no_live_calls`
- Status: `ready_waiting_credentials_or_live_outputs`
- Scenarios: `8`
- P0 scenarios: `7`
- Current blocker scenarios: `5`
- Ready recovery actions: `8`
- Planned live calls: `382`
- Max attempted requests: `764`
- LLM retry token proxy ceiling: `1658856`
- Missing output surfaces: `3`
- Ready to score: `0`
- Ready to promote: `0`
- Live calls performed by builder: `0`
- No secret values written: `True`
- No new metric claim: `True`

| Scenario | Priority | Status | Observation | Recovery action | Success gate |
|---|---|---|---|---|---|
| `missing_credentials` | `P0` | `current_blocker` | credential_ready=False | Set a DashScope/Bailian API key in the live runner environment only, then rerun readiness and runtime environment audits; never write secret values into artifacts. | live_runtime_environment_audit status remains ready and credential_ready becomes true without secret literals. |
| `known_provider_quota_blocker` | `P0` | `current_blocker` | DeepSeek top4/top5 previously failed with AllocationQuota.FreeTierOnly. | Wait for quota/paid tier capacity or choose an explicitly tracked fallback; keep P0 DeepSeek resume blocked until provider capacity is available. | P0 live command finishes without AllocationQuota.FreeTierOnly and output audit sees complete DeepSeek resume rows. |
| `missing_output_clean_run` | `P0` | `current_blocker` | missing_output_surfaces=3; expected_live_calls=382 | Run the current skip-existing, bounded-retry live commands after credentials and quota are ready; preserve the configured output paths. | live_output_audit reports no missing surfaces and no parse/duplicate/extra call errors. |
| `partial_or_invalid_output` | `P0` | `future_recovery_path` | partial_or_invalid_surfaces=0 | Quarantine/archive malformed output JSONL, inspect parse errors, duplicate ids, missing ids, and extra ids, then rerun with --skip-existing-output. | output audit status advances to complete output needing metric/safety scoring instead of partial_or_invalid_output. |
| `retry_exhausted_errors` | `P0` | `future_recovery_path` | max_attempted_requests=764; max_call_attempts=2 | Keep failed rows as evidence, fix the provider-side or transient error, then rerun only missing/failed calls through the skip-existing surface. | failed rows shrink to zero or are explicitly isolated before scoring; call_attempts remain recorded for failed rows. |
| `scoring_blocked_missing_output` | `P0` | `current_blocker` | ready_to_score_steps=0/5 | Run output audit first; only then run the safety/comparison/Omni scoring commands listed by scoring readiness. | ready_to_score_steps reaches the expected scored surfaces and scoring artifacts exist. |
| `promotion_blocked` | `P0` | `current_blocker` | ready_to_promote=0/8 | Promote claims only after output audit, scoring, SLO, and report/PPT traceability all pass; keep smoke/planning rows out of metric claims. | promotion gate marks the relevant live rows ready_to_promote and traceability remains fully covered. |
| `token_or_attempt_budget_ceiling` | `P1` | `planning_guardrail` | max_attempted_requests=764; llm_retry_token_proxy_ceiling=1658856 | Treat 764 attempted requests and the 1.66M prompt-token proxy ceiling as planning ceilings; keep P1 Qwen/Omni expansion behind P0 stability. | live run choice stays within the audited attempt/token/clip proxy budget or records a new budget audit before execution. |

## Reading

- Use this playbook before any post-live claim promotion when credentials, quota, output completeness, scoring, or traceability is uncertain.
- Current blockers are operational gates, not new metric claims.
- Future recovery paths keep partial output and retry exhaustion auditable without blind append or silent overwrite.
- The builder only reads local artifacts; it performs no live/API/model calls and writes no secrets.
