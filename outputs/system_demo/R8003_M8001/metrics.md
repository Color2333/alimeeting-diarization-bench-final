# Realtime Diarization System Metrics

- Execution mode: `offline_replay_existing_fast_slow_outputs_with_rule_writeback`
- Run scope: `single_recording_or_audio`
- Evaluation status: `scored_with_cached_reference`
- Recording: `R8003_M8001`
- Recordings processed: `1`
- Windows processed: `15`
- Cached window coverage: `15/120` (`12.5%`)
- API calls: DeepSeek `0`, Qwen `0`, Omni `0`

| Metric | Value |
|---|---:|
| Fast DER | 45.38% |
| Final DER | 37.21% |
| DER delta vs fast | 8.17 pp |
| Best baseline | slow_base / 38.22% |
| DER delta vs best baseline | 1.01 pp |
| Beats best baseline | True |
| Final Miss | 5.78% |
| Final FA | 24.81% |
| Final Confusion | 6.62% |
| Correction rows | 349 |
| Accepted writebacks | 12 |
| Accepted window corrections | 13 |
| Guard fallback windows | 2 |
| Blocked/deferred/quarantined | 337 |
| First output latency proxy avg / P95 | 0.403s / 0.444s |
| Rule writeback latency proxy avg / P95 | 22.718s / 24.901s |
| Total CLI wall time | 0.062s |

## Reading

- DER/Miss/FA/Conf are scored only when cached AliMeeting reference segments are available.
- Latency values are proxies from existing model runs, not fresh online inference timings.
- The final timeline uses conservative rule recover writeback; guard/quarantine rows do not enter the timeline.
- This run performs zero live LLM/API calls.

## Recording Summary

| Recording | Windows | Fast DER | Final DER | Delta |
|---|---:|---:|---:|---:|
| R8003_M8001 | 15 | 45.38% | 37.21% | 8.17 pp |
