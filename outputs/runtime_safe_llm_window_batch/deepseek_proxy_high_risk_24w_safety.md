# Runtime-Safe LLM Guard Safety

| Windows | Patches | Window decisions | Patch decisions | Harmful accepts | Conservative blocks | Safe blocks | Overrides | Avg call | P95 call | Avg correction | P95 correction |
|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 24 | 136 | quarantine 24 | defer 1 / quarantine 135 | 0 | 127 | 9 | 2 | 10.59s | 17.98s | 35.23s | 46.32s |

## Reading

- The prompt surface passed runtime evidence audit before these calls.
- GT support is joined only here, after the LLM response, to classify safety.
- A conservative block means the patch had true speech/FA support but the guard deferred/rejected/quarantined it.
