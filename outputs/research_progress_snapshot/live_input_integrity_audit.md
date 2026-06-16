# Live Input Integrity Audit

- Runtime contract: `live_input_integrity_audit_no_live_calls`
- Status: `inputs_ready_waiting_credentials_or_quota`
- Surfaces: `3`
- Input-ready surfaces: `3`
- P0 input-ready surfaces: `1`
- Output-missing surfaces: `3`
- DeepSeek resume prompt calls: `139`
- Qwen full prompt calls: `147`
- Omni48 planned calls: `96`
- Recommended policy/workers: `max20` / `8`
- Live calls performed by builder: `0`
- No new metric claim: `True`

| Surface | Priority | Type | Calls | Parents/windows | Input ready | Output status | Writeback right |
|---|---|---|---:|---:|---|---|---|
| `deepseek_resume_inputs` | `P0` | `llm_resume_prompts` | 139/139 | 101/101 | `True` | `missing_output` | `block_or_quarantine_only` |
| `qwen_full_backup_inputs` | `P1` | `llm_full_prompts` | 147/147 | 104/104 | `True` | `missing_output` | `block_or_quarantine_only` |
| `omni48_label_only_inputs` | `P1` | `omni_audio_manifest` | 96/96 | 48/48 | `True` | `missing_output` | `label_only_no_timeline_writeback` |

## Reading

- All three pending live surfaces have complete local inputs; they are waiting on credentials, quota, or live outputs.
- DeepSeek resume is P0 and uses the exported 139-call resume prompt surface.
- Qwen full backup and Omni48 are P1 input-ready surfaces, but they remain fallback/label-only and do not support new metric claims.
- This builder performs no live/API/model calls and writes no secret values.
