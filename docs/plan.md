# Stage 1 — Track 11 / Kazakhtelecom

Stages 1 and 2 are complete by team confirmation. This is the historical Stage 1 plan. Its implemented contracts remain the baseline; current full-task requirements, contract amendments, assignments and the four-stage delivery sequence are in [Stage 3](stage-3.md). Original times below are historical, not current deadlines.
Sources: `seeds/kt/TASK.md`, `seeds/kt/manifest.json`, both case editions, `CONTRACT.md`, inspected kit sources, and the user's track/team decision.
All design choices, schedules, numerical targets and acceptance checks below are [ASSUMPTION] team decisions, not additional requirements from the ТЗ.

## 1. Requirements

The historical requirements below quote the original short brief verbatim. The [full task snapshot](../seeds/kt/TASK.md) and [Stage 3 coverage table](stage-3.md#3-full-task-acceptance-and-actual-rubric) supersede this brief for requirements and scoring; they add mandatory unit classification, conflicts of interest, and Word/PDF/Excel coverage.
> AI agent “Analysis of organizational structure and functions”
> During a reorganization, org charts and regulations are compared by hand, so functions get lost or duplicated. The agent compares the before and after document sets, flags the gaps, and writes a conclusion with links back to the source clauses.
>
> Task owner: Kazakhtelecom

- **R1 — Comparison:** “AI agent “Analysis of organizational structure and functions””; “The agent compares the before and after document sets”.
- **R2 — Gaps:** “functions get lost or duplicated.”; “flags the gaps”. Loss/duplication are the stated problem; exact required classifications remain unconfirmed.
- **R3 — Conclusion and evidence:** “writes a conclusion with links back to the source clauses.”
Historical evaluation note: the short brief contained no criteria or weights. The subsequently consulted full task specifies 25/25/25/15/10; see [Stage 3](stage-3.md). Do not use the old generic scoring assumptions.
Remaining organiser questions: availability/layout of separate annexes or org charts and any prescribed report format. Unit classification and potential conflicts of interest are confirmed must-haves, not unresolved scope questions.

## 2. What we build

- **Function Lineage Auditor** for an internal auditor reviewing a reorganisation [ASSUMPTION]; chosen approach comes from the user's selection.
- Select/upload before and after document sets; demo starts with v8 (Protocol 13, 25.06.2021) → v9 (Protocol 7, 23.12.2022), per manifest (R1).
- Deterministically extract numbered clauses, lettered subclauses, units and explicit reporting relations; preserve source text and hierarchy (R1).
- Align exact text first, then lexical candidates across the complete sets; distinguish edits/moves from potentially missing or duplicated duties (R1–R2).
- The LLM adjudicates only ambiguous candidates and drafts the conclusion; it cannot invent a source, unit or match. Without a key, unresolved pairs remain visible and the conclusion is templated (R2–R3).
- The UI shows a before/after finding table, unit context, uncertainty and a conclusion; every evidence link opens its exact clause and quote (R1–R3).
- Case evidence is anonymised as AO Company and cites Russian law (`v8.txt`/`v9.txt` §§1,3); do not present it as Kazakhtelecom's verified live structure. No separate org-chart file is in `seeds/kt/`.

## 3. Contract

Stage-1 domain extension to `CONTRACT.md`; existing routes, registry and SSE envelope remain unchanged. Batyrkhan owns integration and any shared-core changes.
Reuse `ingest.pipeline.ingest_path`/`ingest_bytes`, existing DOCX/TXT extraction, SQLite, `agent.tools.ToolRegistry`, trace persistence, web upload/timeline components and SSE parsing. No new service, database or dependency is planned.
Important kit boundaries: DOCX `page` is a block ordinal, not a physical page (`ingest/parsers.py`); `/upload` currently requires RAG indexing (`api/routes.py`); keyless `/run` currently emits an error (`CONTRACT.md`). The audit path must run ingestion + deterministic analysis directly, without requiring embeddings or `/run` to succeed.

### Data (JSON; required fields unless explicitly nullable)

```text
Document = {doc: string, doc_id: string, sha256: string, edition: before|after, source: string}
Citation = {doc: string, clause_id: string, quote: string}
ClauseRef = {doc: string, clause_id: string}
Clause = {doc: string, clause_id: string, label: string, parent_id: string|null,
          text: string, ordinal: integer, kind: heading|function|structure|other, unit_ids: string[]}
Unit = {doc: string, unit_id: string, name: string, kind: unit|role,
        parent_unit_id: string|null, citations: Citation[]}
Finding = {id: string, status: unchanged|changed|moved|added|missing|duplicate|unresolved,
           before: ClauseRef[], after: ClauseRef[], citations: Citation[], reason: string,
           method: exact|lexical|llm|human, review_required: boolean}
Report = {run_id: string, mode: deterministic|llm_assisted, documents: Document[],
          clauses: Clause[], units: Unit[], findings: Finding[],
          conclusion: [{text: string, finding_ids: string[], citations: Citation[]}],
          coverage: {before_total: integer, after_total: integer, before_accounted: integer,
                     after_accounted: integer, unresolved: integer}, warnings: string[]}
```

- `doc` is a report-local alias: `v8`/`v9` for the manifest case, otherwise `before-1`/`after-1`, etc.; content identity is the kit's `doc_id` plus full file SHA-256. Never ingest TXT and DOCX exports as two editions of the same input.
- `clause_id` is the numeric path without its final dot (`2.4.1`); letter children use `2.3.1/а` (original Cyrillic). Repeated paths append `@2`, `@3`; unlabelled blocks use `@p<ordinal>`. `label` retains the literal marker; IDs are unique within a document.
- DOCX is the canonical seed source; TXT is a reading aid. Detect embedded markers including `3.10.Рабочие`, but split mid-line only with sentence-boundary and expected sibling/child evidence; `п.`/`пункт`/`разделом` references and dates are not clause markers. Keep joined heading/body text and uncertain boundaries with a warning, never silently drop them. Unit IDs use defining clause IDs; parent links require explicit evidence.
- Quotes are exact substrings of preserved clause text; normalisation is for matching only. Verify `(doc, clause_id, quote)` before publication. Invalid evidence becomes a warning/unresolved finding, never a supported conclusion.
- `missing` means no supported successor found in the supplied after set, not proven organisational loss. `duplicate` means potentially overlapping responsibilities, not repeated wording alone; both require review. Renumbering/movement alone is not loss. Unresolved split/merge candidates retain all candidate refs.
- Every before/after function clause is accounted for in at least one finding; coverage counts unique refs, never row counts. `unchanged` = same text/context; `moved` = preserved function with changed location/owner; `changed` = supported match with content changes; `added` = no supported predecessor. Ambiguity takes `unresolved`, not a forced match.

### Agent tools and HTTP

All tools use the existing typed registry; scope inputs to the current run's documents, not arbitrary filesystem paths.
| Tool | Input | Output |
| --- | --- | --- |
| `parse_regulations` | `{documents: Document[]}` | `{clauses: Clause[], units: Unit[], warnings: string[]}` |
| `align_functions` | `{before_docs: string[], after_docs: string[]}` | `{findings: Finding[]}` from deterministic matching |
| `resolve_alignment` | `{finding_id, before: ClauseRef[], after: ClauseRef[], status, reason}` | `{finding: Finding}`; accept only offered candidate refs/statuses, otherwise keep unresolved |
| `verify_citations` | `{citations: Citation[]}` | `{valid: Citation[], invalid: [{citation: Citation, reason: string}]}` |
| `build_report` | `{finding_ids: string[], conclusion: Report.conclusion|null}` | `Report`; null gives deterministic conclusion, proposed prose must reference verified findings |

`resolve_alignment` validates the LLM's proposed adjudication; it is not a second unbounded agent loop. Quote validity proves provenance, not semantic correctness; LLM decisions stay reviewable.
- **New `POST /audits`**: multipart repeated `before_files` and `after_files`, optional `use_llm=false`; ingest with existing pipeline, then stream existing `Event` frames. `final.data={text: string, payload: Report}`; persist all frames through existing trace storage. Require at least one file per side; errors use the kit JSON envelope before streaming or one terminal `error` afterwards.
- **New `GET /audits/{run_id}`**: return `Report` from the persisted final payload; 404 if absent, 409 if incomplete. Existing `GET /runs/{run_id}/trace` remains the replay route. UI quote links resolve against `Report.clauses` by doc + clause ID; do not invent Word page numbers.
- No key/model failure: complete deterministic report with `mode=deterministic` and a warning; LLM use never gates comparison. Reuse the kit's configured model timeout. Existing Compose/runtime stays; no deployment redesign.

### Ground truth handoff

`seeds/kt/eval/labels.jsonl`: one JSON object per case, `{id, kind: real|synthetic, documents: [{doc, file, sha256}], before: ClauseRef[], after: ClauseRef[], expected_status, citations: Citation[], rationale: string, annotator: string, mutation: null|{operation, source: ClauseRef, description: string}}`.
Use the same status enum and IDs as Finding; refs/citations must resolve in the named fixture. Synthetic fixtures live under `seeds/kt/eval/mutations/`, never overwrite originals. Mark uncertainty `unresolved`; do not label from model output. Compare sets of refs + status, not generated finding IDs or prose. Keep real and synthetic scores separate; citation validity/coverage are not semantic accuracy.
Parser fixtures must cover no-space inline markers, joined heading/body text and prose cross-references that must not split into clauses.

## 4. Individual modules

Time windows below are [ASSUMPTION] work order, not event rules; all three start independently now and stop this stage at 15:30.
Alibi and Askat have ChatGPT access (user update); their modules use ordinary CLI checks, not configured agents/advisors. Batyrkhan owns integration and agent-assisted review; each handoff includes changed paths, commands, actual outputs and limitations.

| Person / ownership | Ordered tasks through 15:30 | R-ids / done check |
| --- | --- | --- |
| **Batyrkhan — core, tools, API, UI, integration**; `apps/api/app/`, `apps/web/`, contract changes and lockfiles | **Now–14:00:** implement domain models and hierarchical parser over existing ingestion; preserve raw clauses and unit references. **14:00–14:30:** deterministic alignment + quote verifier + keyless `/audits` → visible report. **14:30–15:30:** wire the existing registry/model boundary for ambiguous pairs/conclusion, report retrieval and citation navigation; run Alibi's independent fixtures and fix actual failures. | **R1–R3.** Real v8→v9 report without a key, all function clauses accounted for, no invalid published quotes, moved/renumbered fixture not marked missing; browser proof of quote navigation and both real/model-unavailable completion. |
| **Alibi — ground truth and quality measurement**; `seeds/kt/eval/`, `eval/kt/`, `docs/evidence/kt-quality.md` | **Now–14:00:** commit `seeds/kt/eval/labels.jsonl` with the first 10 hand-checked real v8→v9 pairs (§§2.4, 3, 4, 5) in the §3 ground-truth format, exact quotes. **14:00–14:45:** commit `eval/kt/make_mutations.py` (small script, AI-assisted) that writes deletion / duplication / move / renumbering / whitespace-only variants of `v9.txt` into `seeds/kt/eval/mutations/` plus their expected labels; extend real labels to 20. **14:45–15:30:** commit `eval/kt/score.py` comparing a `Report` JSON to `labels.jsonl` (precision / recall / abstentions per status, real and synthetic separately) and the first measured table in `docs/evidence/kt-quality.md`. | **R1–R3.** Every file committed under Alibi's own account; `uv run --no-sync python eval/kt/score.py <report.json>` prints the table; labels predate model output. |
| **Askat — delivery, value and reproducibility**; `docs/architecture.md`, `docs/business-case.md`, `docs/demo.md`, `docs/evidence/kt-launch.md`, `docs/PROGRESS.md`, `scripts/` | **Now–14:00:** commit `docs/architecture.md` (Mermaid diagram of ingest → parse → align → verify → LLM adjudication → report → UI, from §2–§3) and the 14:00 entry in `docs/PROGRESS.md`. **14:00–14:45:** commit `docs/business-case.md` (who uses it in Kazakhtelecom, time saved per reorganisation, pilot path, scaling to every internal regulation and org chart, risks) and `docs/evidence/kt-launch.md` (clean `docker compose up` / `uv` run without personal keys: exact commands and results). **14:45–15:30:** commit `docs/demo.md` (3-minute script: problem → real finding → source quote → unresolved case → keyless mode) and `scripts/demo.sh` that runs the v8→v9 audit through `POST /audits` and saves the `Report` JSON; ask the organiser the §1 questions and record answers in `docs/plan.md` via Batyrkhan. | **Delivery.** Every file committed under Askat's own account; `sh scripts/demo.sh` produces a report file once `/audits` exists; architecture and business case feed README and Demo Day (value 25, scaling 20). |

No cross-owner edits without coordination. Before each commit: `git pull --rebase --autostash`; commit owned paths only and push normally (repository working rules). README/self-deployability, disclosures and hourly evidence are organiser-regulation obligations (5.4.5–5.4.6, 5.4.8, 5.4.15–5.4.16, 5.6.3–5.6.6), not invented track R-ids.

## 5. 14:30 gate

- **Pass [ASSUMPTION]:** both real editions complete ingestion → hierarchical clauses/units → deterministic alignment → citation verification → visible conclusion, with no LLM key; clicking a finding resolves its source quote. Both sides' function coverage is complete or explicitly blocked by a visible parse warning.
- Alibi's first 10 real labels and deletion/duplication/move/renumbering fixtures exercise the live pipeline; record actual agreement and all failures, not an invented accuracy target. Invalid quotes must never appear as supported evidence.
- **Same-track fallback [ASSUMPTION]:** omit optional embeddings and LLM adjudication; use exact + lexical candidate alignment over the full supplied sets, explicit unresolved cases and a deterministic cited conclusion. Keep all R1–R3 outputs and the minimal report UI; no chatbot pivot, hardcoded report or silent subset of clauses.
- If semantic adjudication or chart extraction remains unsupported, expose the limitation and confirm acceptance with the organiser; do not claim unsupported functionality. Current execution follows [Stage 3](stage-3.md), including its explicit contract amendments; [Stage 2](stage-2.md) is historical.
