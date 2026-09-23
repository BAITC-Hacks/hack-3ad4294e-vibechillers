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

