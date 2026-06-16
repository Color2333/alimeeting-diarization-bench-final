# Runtime-Safe LLM Guard Safety

| Windows | Patches | Window decisions | Patch decisions | Harmful accepts | Conservative blocks | Safe blocks | Overrides | Avg call | P95 call | Avg correction | P95 correction |
|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 45 | quarantine 3 | defer 39 / quarantine 6 | 0 | 45 | 0 | 1 | 19.29s | 24.49s | 43.94s | 52.83s |

## Reading

- The prompt surface passed runtime evidence audit before these calls.
- GT support is joined only here, after the LLM response, to classify safety.
- A conservative block means the patch had true speech/FA support but the guard deferred/rejected/quarantined it.
