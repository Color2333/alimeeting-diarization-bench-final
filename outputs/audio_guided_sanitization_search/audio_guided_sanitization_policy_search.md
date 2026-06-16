# Audio-Guided Slow Sanitization Search

- Runtime contract: `audio_guided_slow_sanitization_no_live_calls_audio_features_only`
- Status: `no_robust_audio_sanitizer_found`
- Windows: `120`
- Candidate policies: `56`
- Best policy: `slow`
- Best DER: `16.88%`
- Slow baseline DER: `16.88%`
- Delta vs Slow: `0.00pp`
- Bootstrap P(beats Slow): `0.0%`
- Holdout positive splits: `0/8`
- Holdout weighted delta vs Slow: `0.00pp`

## Top Policies

| Rank | Policy | DER | Miss | FA | Conf | Counters |
|---:|---|---:|---:|---:|---:|---|
| 1 | `slow` | 16.88% | 4.99% | 6.92% | 4.98% | `{"slow_base": 120}` |
| 2 | `audio_support_filter__modemax__min_support_sec0p05` | 17.15% | 5.77% | 6.64% | 4.74% | `{"drop_low_support_sec": 148}` |
| 3 | `audio_support_filter__modemax__min_support_sec0p1` | 17.42% | 6.20% | 6.55% | 4.66% | `{"drop_low_support_sec": 203}` |
| 4 | `audio_support_filter__modemax__min_support_ratio0p05` | 17.46% | 6.00% | 6.66% | 4.80% | `{"drop_low_support_ratio": 122}` |
| 5 | `audio_support_filter__modemax__min_active_channels0p25` | 17.93% | 6.72% | 6.57% | 4.64% | `{"drop_low_active_channels": 157}` |
| 6 | `audio_support_filter__modemean__min_active_channels0p25` | 17.93% | 6.72% | 6.57% | 4.64% | `{"drop_low_active_channels": 157}` |
| 7 | `audio_support_filter__modemax__min_support_sec0p2` | 17.97% | 7.08% | 6.37% | 4.52% | `{"drop_low_support_sec": 288}` |
| 8 | `audio_support_filter__modemax__min_support_ratio0p1` | 18.03% | 6.76% | 6.57% | 4.70% | `{"drop_low_support_ratio": 154}` |
| 9 | `audio_support_filter__modemax__min_support_ratio0p1__min_segment_duration0p2` | 18.04% | 6.85% | 6.53% | 4.67% | `{"drop_low_support_ratio": 103, "drop_short": 100}` |
| 10 | `audio_support_filter__modemax__min_support_ratio0p1__min_support_sec0p1` | 18.14% | 6.98% | 6.51% | 4.66% | `{"drop_low_support_ratio": 9, "drop_low_support_sec": 203}` |
| 11 | `audio_support_filter__modemean__min_support_sec0p05` | 18.37% | 7.48% | 6.38% | 4.52% | `{"drop_low_support_sec": 221}` |
| 12 | `audio_support_filter__modemax__min_support_ratio0p1__min_support_sec0p2` | 18.44% | 7.56% | 6.35% | 4.53% | `{"drop_low_support_ratio": 4, "drop_low_support_sec": 288}` |
| 13 | `audio_support_filter__modemean__min_support_sec0p1` | 19.08% | 8.44% | 6.20% | 4.44% | `{"drop_low_support_sec": 294}` |
| 14 | `audio_support_filter__modemax__min_active_channels0p5` | 19.48% | 8.67% | 6.47% | 4.34% | `{"drop_low_active_channels": 206}` |
| 15 | `audio_support_filter__modemean__min_active_channels0p5` | 19.48% | 8.67% | 6.47% | 4.34% | `{"drop_low_active_channels": 206}` |
| 16 | `audio_support_filter__modemax__min_support_sec0p5` | 20.23% | 10.55% | 5.65% | 4.03% | `{"drop_low_support_sec": 537}` |
| 17 | `audio_support_filter__modemax__min_support_ratio0p1__min_support_sec0p5` | 20.39% | 10.72% | 5.64% | 4.03% | `{"drop_low_support_ratio": 1, "drop_low_support_sec": 537}` |
| 18 | `audio_support_filter__modemax__min_support_ratio0p2` | 21.03% | 10.56% | 6.36% | 4.11% | `{"drop_low_support_ratio": 219}` |
| 19 | `audio_support_filter__modemax__min_support_ratio0p2__min_segment_duration0p2` | 21.05% | 10.64% | 6.33% | 4.08% | `{"drop_low_support_ratio": 166, "drop_short": 100}` |
| 20 | `audio_support_filter__modemax__min_support_ratio0p2__min_support_sec0p1` | 21.08% | 10.66% | 6.34% | 4.08% | `{"drop_low_support_ratio": 56, "drop_low_support_sec": 203}` |

## Reading

- Policies use only audio activity masks and predicted Fast/Slow timelines at runtime.
- DER/GT is used only after materialization for scoring.
- If holdout/bootstrap is weak, this should remain an analysis artifact rather than a default runtime path.
