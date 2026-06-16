# Audio Window Runtime Features

- Runtime contract: `audio_window_energy_features_no_live_calls_no_gt_metrics`
- Status: `pass`
- Windows: `120`
- OK rows: `120`
- Missing audio rows: `0`
- Mean audio speech ratio: `0.329`
- Mean max-channel speech ratio: `0.448`
- Mean channel activity ratio: `0.287`

## Reading

- These are lightweight energy and multichannel activity proxies, not calibrated VAD.
- It can be used as a runtime feature, but DER/GT scoring must happen only after the selector decision.
- Far-field overlapping speech can make the proxy undercount true overlapped speaker time.
