# Three-minute demo

This script is the intended product story. The current checkout can demo
upload, grounded search, citations in the trace, and the keyless degraded path;
the two-edition `/audits` call below is a pending integration contract and must
not be presented as working until Batyrkhan lands it.

## Script

**0:00-0:35 — Problem.** Internal audit and HR need to compare two regulation
editions during a reorganisation. A plausible sentence is not enough: each
finding must point back to its exact clause, and an ambiguous match must remain
unresolved.

**0:35-1:20 — Inputs.** Start the stack, then run `scripts/demo.sh`. It sends
`seeds/kt/v8.docx` and `seeds/kt/v9.docx` to the planned `POST /audits` surface
and writes the returned JSON to `data/demo-report.json`.

**1:20-2:05 — Finding.** Show one returned finding, its source quote, and its
edition/page or clause locator. The presenter must read the quote from the
saved JSON, not invent it from memory.

**2:05-2:35 — Refusal.** Show an unresolved case. The auditor should say that
the evidence is insufficient rather than guess that two similarly worded
functions are equivalent.

**2:35-3:00 — Reproducibility.** Remove `LLM_API_KEY` or use the empty value in
`.env.example`, rerun the health check, and show that the service starts. The
current API guarantees keyless `/healthz`; the current agent reports a readable
error for `/run` without a key.

## Questions for the organiser

- What exact evaluation criteria and judging evidence are required?
- Is a deterministic keyless report with optional LLM adjudication acceptable?

Send the answers to Batyrkhan before presenting the demo. Do not add a
personal key to the repository or the script.