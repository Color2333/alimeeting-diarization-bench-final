# Selector Robustness Diagnosis

- Runtime contract: `selector_robustness_diagnosis_no_live_calls_no_new_scoring`
- Status: `diagnosed_not_robust`
- Diagnosis: `selector_gain_is_real_on_development_pool_but_not_stable_across_recordings`
- Base selector positive recordings: `1/8`
- Base selector holdout positive splits: `1/8`
- Rare runtime selected windows: `3`
- Rare runtime max recording share: `66.7%`
- Rare holdout positive splits: `0/8`

## Blocking Reasons

- `base_selector_gain_not_recording_stable`
- `base_selector_bootstrap_lower_bound_not_positive`
- `rare_overlay_holdout_not_positive`
- `rare_overlay_often_selects_no_heldout_windows`
- `rare_overlay_has_negative_heldout_split`
- `rare_overlay_development_gain_concentrated`

## Next Optimization Direction

- prefer features that fire on multiple recordings rather than sparse single-recording gains
- require leave-one-recording selected-window coverage before promoting a rare overlay
- treat additional threshold tuning on the same 120-window pool as low-value unless it improves holdout splits
- prioritize calibrated VAD/speaker-activity features or new held-out recordings for stronger selector evidence

## Rare Runtime Selected Windows

| Window | Recording | Base DER | Overlay DER | Delta |
|---|---|---:|---:|---:|
| `R8007_M8011:30:0` | `R8007_M8011` | 3.24% | 2.92% | 0.32pp |
| `R8007_M8011:30:8` | `R8007_M8011` | 42.66% | 34.16% | 8.50pp |
| `R8009_M8019:30:12` | `R8009_M8019` | 3.33% | 1.58% | 1.75pp |
