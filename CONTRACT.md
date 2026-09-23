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
