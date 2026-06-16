# Runtime-Safe LLM Guard Safety

| Windows | Patches | Window decisions | Patch decisions | Harmful accepts | Conservative blocks | Safe blocks | Overrides | Avg call | P95 call | Avg correction | P95 correction |
|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 60 | quarantine 4 | defer 28 / quarantine 32 | 0 | 60 | 0 | 0 | 33.17s | 44.00s | 57.81s | 72.33s |

## Reading

- The prompt surface passed runtime evidence audit before these calls.
- GT support is joined only here, after the LLM response, to classify safety.
- A conservative block means the patch had true speech/FA support but the guard deferred/rejected/quarantined it.
