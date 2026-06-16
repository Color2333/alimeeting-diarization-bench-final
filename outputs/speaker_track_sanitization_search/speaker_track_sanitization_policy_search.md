# Speaker-Track Sanitization Search

- Runtime contract: `speaker_track_sanitization_no_live_calls_prediction_features_only`
- Status: `no_robust_speaker_track_sanitizer_found`
- Policy set: `core`
- Candidate policies: `25`
- Best policy: `speaker_track_filter__min_track_total_sec0p5__require_remaining_speakers1`
- Best DER: `16.87%`
- Slow DER: `16.88%`
- Delta vs Slow: `0.007pp`
- Bootstrap P(beats Slow): `67.0%`
- Bootstrap CI: `-0.021pp` to `0.041pp`
- Holdout positive splits: `0/8`
- Holdout weighted delta: `-0.013pp`
- Score cache hits/misses: `3000.0/0.0`

## Top Policies

| Rank | Policy | DER | Delta vs Slow | Pred segs | Counters |
|---:|---|---:|---:|---:|---|
| 1 | `speaker_track_filter__min_track_total_sec0p5__require_remaining_speakers1` | 16.87% | 0.007pp | 11.19 | `{"dropped_segments": 11, "dropped_speaker_tracks": 11, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 2 | `slow` | 16.88% | 0.000pp | 11.28 | `{"score_cache_hits": 120, "score_cache_misses": 0, "slow_base": 120}` |
| 3 | `speaker_track_filter__min_track_max_segment_sec0p5__require_remaining_speakers1` | 16.88% | -0.003pp | 11.09 | `{"dropped_segments": 23, "dropped_speaker_tracks": 15, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 4 | `speaker_track_filter__min_track_fast_overlap_sec0p1__require_remaining_speakers1` | 16.94% | -0.060pp | 11.20 | `{"dropped_segments": 10, "dropped_speaker_tracks": 6, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 5 | `speaker_track_filter__min_track_total_sec1p0__require_remaining_speakers1` | 16.95% | -0.072pp | 11.01 | `{"dropped_segments": 33, "dropped_speaker_tracks": 23, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 6 | `speaker_track_filter__min_track_total_sec2p0__require_remaining_speakers1` | 17.02% | -0.138pp | 10.89 | `{"dropped_segments": 47, "dropped_speaker_tracks": 28, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 7 | `speaker_track_filter__min_track_max_segment_sec1p0__require_remaining_speakers1` | 17.03% | -0.146pp | 10.88 | `{"dropped_segments": 48, "dropped_speaker_tracks": 27, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 8 | `speaker_track_filter__min_track_fast_overlap_sec0p5__require_remaining_speakers1` | 17.08% | -0.202pp | 11.07 | `{"dropped_segments": 25, "dropped_speaker_tracks": 13, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 9 | `speaker_track_filter__min_track_fast_overlap_ratio0p05__require_remaining_speakers1` | 17.09% | -0.205pp | 11.15 | `{"dropped_segments": 16, "dropped_speaker_tracks": 6, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 10 | `speaker_track_filter__min_track_total_sec0p5__min_track_fast_overlap_ratio0p05__require_remaining_speakers1` | 17.09% | -0.211pp | 11.08 | `{"dropped_segments": 24, "dropped_speaker_tracks": 14, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 11 | `speaker_track_filter__min_track_total_sec1p0__min_track_fast_overlap_ratio0p05__require_remaining_speakers1` | 17.16% | -0.283pp | 10.91 | `{"dropped_segments": 45, "dropped_speaker_tracks": 25, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 12 | `speaker_track_filter__min_track_total_sec2p0__min_track_fast_overlap_ratio0p05__require_remaining_speakers1` | 17.23% | -0.349pp | 10.79 | `{"dropped_segments": 59, "dropped_speaker_tracks": 30, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 13 | `speaker_track_filter__min_track_fast_overlap_ratio0p1__require_remaining_speakers1` | 17.44% | -0.562pp | 11.11 | `{"dropped_segments": 21, "dropped_speaker_tracks": 7, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 14 | `speaker_track_filter__min_track_total_sec0p5__min_track_fast_overlap_ratio0p1__require_remaining_speakers1` | 17.45% | -0.568pp | 11.04 | `{"dropped_segments": 29, "dropped_speaker_tracks": 15, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 15 | `speaker_track_filter__min_track_total_sec1p0__min_track_fast_overlap_ratio0p1__require_remaining_speakers1` | 17.52% | -0.640pp | 10.87 | `{"dropped_segments": 50, "dropped_speaker_tracks": 26, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 16 | `speaker_track_filter__min_track_total_sec2p0__min_track_fast_overlap_ratio0p1__require_remaining_speakers1` | 17.59% | -0.705pp | 10.75 | `{"dropped_segments": 64, "dropped_speaker_tracks": 31, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 17 | `speaker_track_filter__min_track_segments2__require_remaining_speakers1` | 20.64% | -3.754pp | 11.00 | `{"dropped_segments": 34, "dropped_speaker_tracks": 34, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 18 | `speaker_track_filter__min_track_total_sec0p5__min_track_segments2__require_remaining_speakers1` | 20.64% | -3.754pp | 11.00 | `{"dropped_segments": 34, "dropped_speaker_tracks": 34, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 19 | `speaker_track_filter__min_track_total_sec1p0__min_track_segments2__require_remaining_speakers1` | 20.66% | -3.776pp | 10.87 | `{"dropped_segments": 50, "dropped_speaker_tracks": 40, "score_cache_hits": 120, "score_cache_misses": 0}` |
| 20 | `speaker_track_filter__min_track_total_sec2p0__min_track_segments2__require_remaining_speakers1` | 20.71% | -3.830pp | 10.76 | `{"dropped_segments": 63, "dropped_speaker_tracks": 44, "score_cache_hits": 120, "score_cache_misses": 0}` |

## Reading

- Policies remove entire low-evidence Slow speaker tracks using only prediction-derived features.
- `no_robust_speaker_track_sanitizer_found` means this new candidate surface should not be promoted yet.
