# Live Token Quota Budget Audit

- Runtime contract: `live_token_quota_budget_audit_no_live_calls`
- Status: `quota_proxy_ready_waiting_credentials_or_quota`
- Token proxy policy: `prompt_chars_div4_proxy_not_provider_billing_tokens`
- Surfaces: `3`
- LLM prompt calls: `286`
- LLM token proxy chars/4: `829428`
- LLM retry token proxy ceiling: `1658856`
- P0 retry token proxy ceiling: `801724`
- Omni48 retry clip-model seconds ceiling: `1536.0`
- Max attempted requests: `764`
- Live calls performed by builder: `0`
- No new metric claim: `True`

| Surface | Priority | Type | Calls | Parents | Prompt chars | Token proxy | Attempts | Retry token/clip ceiling |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `deepseek_resume_after_top3` | `P0` | `llm_prompt_jsonl` | 139 | 101 | 1603450 | 400862 | 2 | 801724 |
| `qwen_full_backup` | `P1` | `llm_prompt_jsonl` | 147 | 104 | 1714264 | 428566 | 2 | 857132 |
| `omni48_label_only` | `P1` | `omni_audio_call_manifest` | 96 | 48 | n/a | n/a | 2 | 1536.0 |

## Reading

- Token proxy is estimated from local prompt text as characters divided by four; it is not provider billing truth.
- Under the current 2-attempt policy, the two LLM live surfaces have a combined retry token proxy ceiling of 1658856.
- P0 DeepSeek resume alone has a retry token proxy ceiling of 801724; Qwen backup remains P1 fallback-only.
- Omni48 is represented by clip-model seconds, not text tokens; its 2-attempt ceiling is 1536.0 clip-model seconds.
- The builder only reads local artifacts; it performs no live/API/model calls and writes no secrets.
