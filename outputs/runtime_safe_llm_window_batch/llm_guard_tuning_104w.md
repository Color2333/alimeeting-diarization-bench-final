# LLM Guard Tuning Analysis

## Current 104w Guard

- Windows: 104
- Patches: 1917
- Current safety: conservative_block 1811 / safe_accept 63 / safe_block 43
- Current window decisions: quarantine 1740 / review 177

## Candidate Policies

| Policy | Candidate accepts | Conservative recovered | Harmful accepts | Safe accepts after | Conservative after | Verdict | Predicate |
|---|---:|---:|---:|---:|---:|---|---|
| review_support_ge_0.5_non_suppress | 104 | 104 | 0 | 167 | 1707 | candidate_zero_harm_sample | review windows; non-suppress patches; cross-model support >= 0.5 |
| review_support_ge_0.8_non_suppress | 94 | 94 | 0 | 157 | 1717 | candidate_zero_harm_sample | review windows; non-suppress patches; cross-model support >= 0.8 |
| keep_fast_supported_ge_0.5_passthrough | 165 | 165 | 0 | 228 | 1646 | candidate_zero_harm_sample | keep_fast_supported passthrough; cross-model support >= 0.5 |
| keep_fast_supported_ge_0.9_passthrough | 136 | 136 | 0 | 199 | 1675 | candidate_zero_harm_sample | keep_fast_supported passthrough; cross-model support >= 0.9 |
| combined_review0.5_keepfast0.5 | 260 | 260 | 0 | 323 | 1551 | candidate_zero_harm_sample | review non-suppress support >= 0.5, plus keep_fast_supported passthrough support >= 0.5 |
| combined_review0.8_keepfast0.9 | 222 | 222 | 0 | 285 | 1589 | candidate_zero_harm_sample | review non-suppress support >= 0.8, plus keep_fast_supported passthrough support >= 0.9 |
| negative_quarantine_support_ge_0.95 | 1134 | 1117 | 17 | 1180 | 694 | negative_control_or_reject | negative control: quarantine non-suppress patches with support >= 0.95 |

## Reading

- Policies use deployable fields only: LLM window decision, patch type, and cross-model support.
- GT support is used only after the policy simulation to label safe vs harmful accepts.
- The negative control shows why high support alone is not enough inside quarantine windows.
- `keep_fast_supported` passthrough should be treated as preserving an already visible fast segment, not writing a new slow timestamp.
