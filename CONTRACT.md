# Cross-slice contract

Binding for every slice. Anything not fixed here is the slice owner's call; anything fixed here is changed only by
the integrator.

## Layout and ownership

| Path | Owner slice |
| --- | --- |
| `apps/api/app/{config,db,events}.py` | integrator (already written, import it, do not edit) |
| `apps/api/app/main.py`, `apps/api/app/api/` | ApiCore |
| `apps/api/app/agent/` | AgentLoop |
| `apps/api/app/rag/` | RagCore |
| `apps/api/app/ingest/` | Ingest |
| repo root, `apps/*/Dockerfile`, `.github/` | Packaging |
| `apps/web/` | Web |

No slice edits another slice's files. Missing counterpart function → import it and code against the signature below;
it will exist at integration.

## Environment

Python 3.12 only, dependencies already locked and installed at `kit/.venv`.
Run things as `uv run --no-sync python -c ...` or `uv run --no-sync pytest apps/api/tests/test_<yours>.py`.
**Never run `uv add`, `uv sync`, `uv lock`** — a new dependency is a request to the integrator, not an edit.

Env variable names (already in `config.Settings`): `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_S`,
`LLM_MAX_TOKENS`, `DB_PATH`, `DATA_DIR`, `SEEDS_DIR`, `EMBED_MODEL`, `EMBED_DIM`, `API_HOST`, `API_PORT`,
`CORS_ORIGINS`. Web uses `NEXT_PUBLIC_API_BASE`.

## Event envelope

`apps/api/app/events.py` — `Event(type, run_id, data, seq, ts)`, `event.to_sse()`, `SequenceCounter`.
Types: `status`, `token`, `tool_call`, `tool_result`, `citation`, `final`, `error`, with the `data` shapes documented
in that file. The SSE frame carries `event: <type>` and a JSON `data:` line. This is the only wire format.

## Interfaces

```python
# agent/tools.py  (AgentLoop owns the registry; other slices only register into it)
@dataclass
class Tool:
    name: str
    description: str
    params: type[pydantic.BaseModel]
    fn: Callable[..., Any]          # sync or async, returns JSON-serialisable

class ToolRegistry:
    def register(self, tool: Tool) -> None: ...
    def get(self, name: str) -> Tool: ...
    def list(self) -> list[Tool]: ...

# agent/loop.py
async def run_agent(
    prompt: str,
    *,
    run_id: str,
    registry: ToolRegistry,
    history: list[dict] | None = None,
) -> AsyncIterator[Event]: ...
    # yields Events in seq order, terminates with exactly one `final` or one `error`,
    # and persists every event into agent_trace.

# rag/chunk.py  (RagCore owns splitting; Ingest imports it)
def split_pages(
    pages: list[dict],               # [{"page": int, "text": str}]
    *, target_chars: int = 1200, overlap: int = 150,
) -> list[dict]: ...                 # [{"ordinal": int, "page": int|None, "text": str}]

# rag/search.py
@dataclass
class Hit:
    chunk_id: str
    doc_id: str
    text: str
    score: float
    source: str
    page: int | None

def search(query: str, k: int = 10) -> list[Hit]: ...
def index_document(doc_id: str) -> int: ...      # chunks+embeds rows already in `chunks`, returns count
def register_tools(registry) -> None: ...        # exposes `search_documents`

# ingest/pipeline.py
@dataclass
class ParsedDoc:
    doc_id: str
    source: str
    title: str | None
    media_type: str
    pages: list[dict]        # [{"page": int, "text": str}]

def ingest_path(path: str | Path, *, source: str | None = None) -> ParsedDoc: ...
    # parses, writes `documents` + `chunks` rows, returns the doc; caller triggers rag.index_document
def supported_suffixes() -> set[str]: ...
```

## HTTP surface (ApiCore)

- `GET /healthz` → `{"status":"ok","llm_configured":bool,"db":"ok","version":str}`; 200 even without an LLM key.
- `POST /run` body `{"prompt": str, "history": [...]|null}` → `text/event-stream` of the envelope above.
- `GET /runs/{run_id}/trace` → `{"run_id":..., "events":[...]}` replayed from SQLite.
- `POST /upload` multipart `file` → `{"doc_id":..., "chunks":int, "pages":int}`.
- Errors: JSON `{"error": {"message": str, "type": str}}`, never a bare stack trace.

## Degraded path (all slices)

No `LLM_API_KEY` must never crash the process: `/healthz` reports `llm_configured: false`, `/run` emits one `error`
event with a readable message. The judge runs this without our key.

## Rules

- Pin nothing new, install nothing new, do not touch `pyproject.toml`/`uv.lock`.
- No repo-wide lint or test runs; exercise your own slice and paste the output.
- Keep to the locked stack: PyMuPDF is banned (AGPL), no Qdrant/pgvector, no observability servers, no auth.
- Real logic only. A stub, a mock or a hardcoded answer on the main path is a failed slice.

## Stage 3 audit contract (2026-09-23)

This amendment supersedes earlier ownership: Batyrkhan owns backend/shared models/runtime/dependencies;
Askat owns `apps/web/`, export and delivery; Alibi owns evaluation and gold. No concurrent frontend edits
by backend builders. The Pydantic wire source is `apps/api/app/audit/models.py`.

Existing seven Finding statuses, ClauseRef, Citation `{doc, clause_id, quote}`, and
Report.mode `deterministic|llm_assisted` are unchanged. New fields:

```text
UnitRef = {doc: string, unit_id: string}
SourceLocation = {page: integer|null, block: integer|null, sheet: string|null, cell_range: string|null}
Clause.location: SourceLocation|null
UnitChange = {id, status: retained|reorganised|created|unresolved,
  before: UnitRef[], after: UnitRef[], citations: Citation[], reason,
  method: exact|lexical|llm|human, review_required: boolean}
Risk = {id, kind: potential_duplication|potential_conflict_of_interest,
  units: UnitRef[], refs: ClauseRef[], citations: Citation[], reason,
  method: exact|lexical|llm|human, review_required: true}
Report.unit_changes: UnitChange[]
Report.risks: Risk[]
ConclusionItem.unit_change_ids: string[]
ConclusionItem.risk_ids: string[]
Report.agent = {status: not_requested|completed|partial|unavailable|failed,
  model: string|null, turns: integer, tool_calls: integer,
  investigated_finding_ids: string[], stop_reason: string}
```

Old saved Reports accept omitted additions: lists default empty, Clause.location and Report.agent default
null. **Null/missing agent means Stage 3 not assessed**, not "no risks". Every new producer explicitly sets
AgentExecution, including keyless `not_requested` and requested-but-unavailable. Completed means a bounded
investigation finished, not that every finding was reviewed. Capped/unreviewed scope is disclosed.

`POST /audits` retains multipart `before_files`, `after_files`, `use_llm`; `GET /audits/{run_id}` returns
the saved Report. Audit API alone sequences and persists SSE, with exactly one `final` or `error`;
`final.data={text, payload: Report}`. `/runs/{run_id}/trace` remains replayable. Tool events carry actual
model-selected names, arguments and results, not fabricated calls or hidden reasoning.

Host parses and aligns once. Audit investigation registry excludes reset-capable parse/align tools.
The shared conversation engine must not persist audit events or apply `/run` search-hit citation rules.
Default investigation bounds: 12 model turns, 32 tool calls, 180 seconds, plus LLM_TIMEOUT_S per request.
Validated partial decisions survive failures; unavailable/failed deterministic fallback is never completed.
Tool mutations are committed only after successful completion on isolated mutable state; a cancelled/deadline
tool cannot modify the report later. Finalization requires nonempty inspection evidence from an earlier model
turn, not a blind inspect/finalize batch. Model rationale stays in the trace; published alignment explanations
are generated from validated statuses/refs. Audit final is emitted only after successful SQLite persistence.

Unit refs resolve to correct-edition structural units; mentioned roles cannot establish unit lineage.
Created needs predecessor search; renamed/split/merged units need cited change evidence. Before-only units
remain unresolved without dissolution evidence. Risks concern after-set duties, may reference units/roles,
and require exact citations to duties and incompatibility basis. Cooperation and "control" alone do not prove
a conflict. All recommendations remain advisory, subject to responsible human review.

Source locations use physical PDF pages, 1-based DOCX body block ordinals, or workbook sheet/cell ranges.
Unknown values remain null. Exact quote and ClauseRef validation remains mandatory.
DOCX physical pages are never fabricated. Legacy `.doc`/`.xls` require conversion; empty/unreadable annexes
fail rather than produce a successful empty report. Tables use explicit column/merged-owner metadata; formulas
are preserved as source strings, not evaluated or inferred into duties. Image-only PDF support depends on the
available local OCR runtime; geometric PDF tables/diagrams are not claimed as supported structure.
