# Runtime-Safe LLM Guard Safety

| Windows | Patches | Window decisions | Patch decisions | Harmful accepts | Conservative blocks | Safe blocks | Overrides | Avg call | P95 call | Avg correction | P95 correction |
|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 104 | 1917 | quarantine 96 / review 8 | accept 63 / defer 732 / quarantine 1122 | 0 | 1811 | 43 | 2 | 20.27s | 35.52s | 44.92s | 63.85s |

## Reading

- The prompt surface passed runtime evidence audit before these calls.
- GT support is joined only here, after the LLM response, to classify safety.
- A conservative block means the patch had true speech/FA support but the guard deferred/rejected/quarantined it.
