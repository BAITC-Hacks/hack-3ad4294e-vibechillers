# Three-minute demo

This is the planned two-edition demo, not a completed live rehearsal.
Follow README host prerequisites and the isolated launch procedure in
`docs/evidence/kt-launch.md`; runtime and UI acceptance remain pending.

## Script

**0:00-0:35 — Problem.** Internal audit and HR need to compare two regulation
editions during a reorganisation. A plausible sentence is not enough: each
finding must point back to its exact clause, and an ambiguous match must remain
unresolved.

**0:35-1:20 — Inputs.** Start the stack, then run `bash scripts/demo.sh`. It sends
`v8.docx` as `before_files` and `v9.docx` as `after_files` to `POST /audits`,
with `use_llm=false`, and writes the verified final payload to
`data/demo-report.json`.

**1:20-2:05 — Finding.** Show one returned finding, both before/after refs,
its source quote, and the exact clause locator. The presenter must read the
quote from the saved JSON, not invent it from memory.

**2:05-2:35 — Refusal.** Show an unresolved case. The auditor should say that
the evidence is insufficient rather than guess that two similarly worded
functions are equivalent.

**2:35-3:00 — Reproducibility.** Run
`uv run --no-sync python scripts/export_report.py --report data/demo-report.json
--out data/demo-report.html`, open the HTML without the server, then call
`GET /audits/{run_id}` and compare the complete JSON using the README command.
Before starting Compose, explicitly clear the shell's `LLM_API_KEY` as well
as the `.env` value. The expected no-model behavior is a deterministic Report;
`use_llm=true` should add a fallback warning. Confirm this on the live stack
before presenting it as a measured result.

## Questions for the organiser

- What exact evaluation criteria and judging evidence are required?
- Is a deterministic keyless report with optional LLM adjudication acceptable?

Send the answers to Batyrkhan before presenting the demo. Do not add a
personal key to the repository or the script.