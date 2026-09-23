# Function Lineage Auditor: architecture

The current repository implements the two-edition audit path as a public,
keyless HTTP workflow. It parses both uploads, aligns function clauses,
verifies citations, emits a Report through SSE, persists it, and serves it
again through `GET /audits/{run_id}`. Optional LLM adjudication is bounded and
does not gate the deterministic Report.

```mermaid
flowchart LR
    A[Before/after DOCX/PDF/XLSX/CSV/TXT] --> B[POST /audits]
    B --> C[Parse pages]
    C --> D[Chunk and persist]
    D --> E[SQLite audit run and trace]
    E --> F[Align functions]
    F --> G[Verify citations]
    G --> H[Optional bounded LLM adjudication]
    H --> I[Report: findings, conclusion, warnings]
    I --> J[Next.js report UI]
    I --> K[GET /audits/{run_id}]
```

| Component | Responsibility | Current repository boundary |
| --- | --- | --- |
| Ingest | Accept before/after files and store parsed inputs | `POST /audits`, `api/audits.py` |
| Parse | Extract page/block text and media type | `ingest/parsers.py` |
| Align | Compare function clauses and preserve candidate refs | `audit/align.py`; weak cases remain unresolved |
| Verify citations | Check exact `(doc, clause_id, quote)` provenance | `audit/report.py` |
| LLM adjudication | Optional bounded interpretation of ambiguous findings | `agent/audit_llm.py`; deterministic fallback remains |
| Report | Preserve findings, citations, coverage, warnings and conclusion | `audit/models.py`, `api/audits.py` |
| UI | Upload editions, inspect findings, open both clauses, reopen saved report | `AuditWorkspace.tsx`, `AuditReport.tsx` |
| Offline export | Render public Report JSON with findings, conclusion, warnings, roles/units and their source citations | `scripts/export_report.py`; standard library, no SQLite access or external assets |

The binding audit contract is in `docs/plan.md` §3: repeated multipart
`before_files` and `after_files` to `POST /audits`, one terminal `final` event
whose `data.payload` is the Report, and `GET /audits/{run_id}` for retrieval.
Missing `LLM_API_KEY` is a supported deterministic mode. Existing kit routes
and trace persistence remain available alongside the audit routes.