# Realtime Diarization System Metrics

- Execution mode: `offline_replay_existing_fast_slow_outputs_with_rule_writeback`
- Evaluation status: `no_cached_model_outputs`
- Recording: `None`
- Windows processed: `0`
- API calls: DeepSeek `0`, Qwen `0`, Omni `0`

| Metric | Value |
|---|---:|
| Fast DER | n/a |
| Final DER | n/a |
| DER delta vs fast | n/a |
| Final Miss | n/a |
| Final FA | n/a |
| Final Confusion | n/a |
| Correction rows | 0 |
| Accepted writebacks | 0 |
| Blocked/deferred/quarantined | 0 |
| First output latency proxy avg / P95 | 0.000s / 0.000s |
| Rule writeback latency proxy avg / P95 | 0.000s / 0.000s |
| Total CLI wall time | 0.050s |

## Reading

- DER/Miss/FA/Conf are scored only when cached AliMeeting reference segments are available.
- Latency values are proxies from existing model runs, not fresh online inference timings.
- The final timeline uses conservative rule recover writeback; guard/quarantine rows do not enter the timeline.
- This run performs zero live LLM/API calls.
