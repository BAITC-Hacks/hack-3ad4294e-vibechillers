# Function Lineage Auditor: architecture

## Public audit path

```mermaid
flowchart LR
    A[Комплекты до и после: DOCX/PDF/XLSX] --> B[POST /audits]
    B --> C[Извлечение и сохранение источников]
    C --> D[Детерминированное сопоставление и проверка цитат]
    D --> E[Опциональное исследование моделью]
    E --> F[Report и единственное terminal event]
    F --> G[Русский reviewer workspace]
    F --> H[SQLite: Report и события]
    H --> I[GET /audits/id и /runs/id/trace]
    I --> G
    F --> J[Сохранённый JSON]
    J --> K[Стандартно-библиотечный offline HTML]
```

Backend owns domain decisions and evidence validation. The browser and exporter do not invent unit transitions, risk classifications, findings, model actions or a second Report format. The Stage 3 schema handoff is `4da4390`; the wire source is `apps/api/app/audit/models.py`, with the HTTP/SSE amendment in `CONTRACT.md`.

## Consumer boundaries

| Boundary | Implementation and invariant |
| --- | --- |
| Upload | `AuditWorkspace.tsx` / `UploadDropzone.tsx`: repeated `before_files` and `after_files`, `use_llm`; DOCX/PDF/XLSX plus TXT reading aid. DOC/XLS require conversion, not renaming. |
| Wire gate | `lib/api.ts`: validates nested Report types and unique source/result IDs before rendering; preserves absent fields and `agent: null` for old reports. |
| Reviewer | `AuditReport.tsx`: 25-row pages, search/status/review filters, N:M unit transitions, function findings, separately typed cross-unit risks, conclusion links to each output type. No summed duplication metric for overlapping finding/risk evidence. |
| Sources | `lib/audit.ts`: document-scoped indexes, exact substring checks, defining role/unit citations, parent/neighbor context. Only supplied PDF page, DOCX block or sheet/cell coordinates are shown; unknown locations are not invented. |
| Agent visibility | `Report.mode` and `Report.agent` are distinct. Completed/partial/unavailable/failed/not_requested, stop reason and investigated subset are shown as supplied. Completed is not full-document review. Missing/null agent and historical empty additions mean not assessed. |
| Actions | Existing SSE and persisted trace only: real tool name, arguments, result and public reason. Token/internal SDK span content is not displayed as reasoning. Host status messages do not prove model participation. Reopening is explicitly replay, not a new run. |
| Bounded UI operations | Five-minute audit connection deadline, thirty-second report/trace opening deadline, cancellation and stale-response guards. A terminal event ends waiting; truncated/empty streams surface errors. Cancellation does not claim server-side cancellation. |
| Persistence | Report and trace come from separate public endpoints. Report JSON download/local import retains all public fields; local files (up to 50 MiB) are not uploaded. A missing trace stays visibly missing rather than synthesized from counters. |
| Offline export | `scripts/export_report.py`: JSON only, no SQLite, no model calls or external assets. Escaped text, CSP, hash-based fragment IDs, exact-source checks, visible edition/role mismatch warnings and duplicate-ID rejection. All findings, units, changes, risks, conclusion links, locations, warnings and agent metadata remain inspectable. |

## Implemented versus integrated

The new frontend/export consumers implement the published Stage 3 shape. The `4da4390` handoff adds schemas, not the completed Stage 3 producer: the exercised API still returns no unit changes/risks and `agent: null`. Current model orchestration remains the Stage 2 pass until Batyrkhan's agent integration lands. The UI does not label these results as a successful Stage 3 agent audit.

Real DOCX upload, persistence, both-side source navigation and keyless fallback were exercised locally; controlled PDF text is extracted and matched. The controlled two-column XLSX probe exposes missing table semantics, and PDF/XLSX locations remain null in that backend. These are backend integration blockers with reproduction in [launch evidence](evidence/kt-launch.md), not frontend-generated substitutes. Synthetic local JSON checks only consumer navigation and safety.

## Security and ownership

Batyrkhan owns backend, contracts, root runtime and dependency manifests/locks; Alibi owns evaluation/control/gold; Askat owns frontend/export/delivery. Local verification binds both servers to loopback. No unauthenticated public deployment, document transfer to a new provider or paid inference is authorised by this architecture. An approved judge-accessible agent route remains a separate release gate.
