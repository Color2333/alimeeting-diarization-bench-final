# Live Provider Routing Decision

- Runtime contract: `live_provider_routing_decision_no_live_calls_no_secret_values`
- Status: `blocked_no_default_primary_provider`
- Route rows: `4`
- Recommended default execute scope: `none`
- DeepSeek no-go: `True`
- DeepSeek planned calls not selected: `139`
- Qwen fallback calls: `147`
- Omni label calls: `96`
- Credential ready: `False`
- Ready runs: `0`
- Missing output surfaces: `3`
- No live calls performed: `True`
- No scoring commands executed: `True`
- No new metric claim: `True`

| Route | Provider | Scope | Status | Default | Calls | Boundary |
|---|---|---|---|---|---:|---|
| `deepseek_resume_primary` | `deepseek-v4-flash` | `deepseek` | `no_go_current` | `False` | 139 | `do_not_use_deepseek_api_by_default` |
| `qwen_full_backup_optional` | `qwen3.6-flash-2026-04-16` | `qwen` | `fallback_candidate_blocked_credentials` | `False` | 147 | `fallback_only_not_primary_latency_claim` |
| `omni48_label_only` | `qwen3.5-omni-flash/qwen3.5-omni-plus` | `omni` | `label_only_candidate_blocked_credentials` | `False` | 96 | `label_only_no_timeline_writeback` |
| `default_live_execute` | `none` | `none` | `blocked_no_default_primary_provider` | `False` | 0 | `default_execute_blocked_by_provider_route` |

## Reading

- This artifact overrides stale default execution wording with the current provider route decision.
- DeepSeek is not selected for default live execution while the phase scorecard records the API no-go boundary.
- Qwen and Omni remain explicit fallback/label-only routes after credentials are ready; neither can promote primary latency claims by itself.
