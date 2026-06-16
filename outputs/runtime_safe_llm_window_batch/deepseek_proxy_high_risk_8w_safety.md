# Runtime-Safe LLM Guard Safety

| Windows | Patches | Window decisions | Patch decisions | Harmful accepts | Conservative blocks | Safe blocks | Avg call | P95 call | Avg correction | P95 correction |
|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 8 | 78 | quarantine 8 | quarantine 78 | 0 | 77 | 1 | 11.98s | 16.74s | 36.62s | 45.07s |

## Reading

- The prompt surface passed runtime evidence audit before these calls.
- GT support is joined only here, after the LLM response, to classify safety.
- A conservative block means the patch had true speech/FA support but the guard deferred/rejected/quarantined it.
