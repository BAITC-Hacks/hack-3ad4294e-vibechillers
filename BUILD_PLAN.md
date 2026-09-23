# Build plan — kit on qwen3.8-flash-next

Operator runs this from `C:/Users/sydyk/Downloads/kit`. Every task below is one file, one signature set, one
acceptance command. The model is fast and literal: the plan carries the design, the model carries the typing.

Already written and frozen: `pyproject.toml`, `uv.lock`, `.python-version`, `.env`, `.gitignore`, `CONTRACT.md`,
`.omp/{AGENTS.md,config.yml,agents/}`, `apps/api/app/{config,db,events}.py`, empty package tree, `apps/api/tests/`.
Verified on this machine: `openai-agents 0.22.3`, `fastapi 0.141.1`, `sentence-transformers 6.1.0`,
`sqlite-vec v0.1.9` loads and `enable_load_extension` works, schema initialises, `.env` resolves with
`llm_configured=True` against `https://xllm.sek.su/v1` (`anthropic/claude-haiku-4-5`).

## How to run it — autonomous, no operator in the loop

The session driving this plan runs unattended. It decides nothing about design (the design is here and in
`CONTRACT.md`); it dispatches, verifies, commits and moves on.

- **Subagents are unlimited.** Spawn as many `builder` agents as there is independent work — the whole wave at
  once, and extra ones for anything a task turns out to contain. They are the same model as the driver, so there is
  no reason to hoard them. What is never allowed is two agents editing one file.
- `.omp/config.yml` routes every builder to `qwen3.8-flash-next:high` with an Opus advisor watching. Nothing model
  related is passed per task.
- Batch `context` for every wave: *"Working directory `C:/Users/sydyk/Downloads/kit`. `CONTRACT.md` is binding.
  Python 3.12 at `.venv`; run commands as `uv run --no-sync …`. Never run `uv add`/`uv sync`/`uv lock`. Never edit
  a file owned by another task. Paste the literal output of your acceptance command in your final message."*
- After every wave the driver runs the wave's check itself, then commits:
  `git add -A && git commit -m "feat(wave-N): <what landed>"`. The repository is local, already initialised, and
  the first commit `aad751e` holds the frozen core. Commit even when part of the wave failed — the message says
  which tasks are missing, and a commit per wave is what makes the night reviewable in the morning.
- A failing task is re-dispatched once with the failure text pasted in. If it fails twice, commit the wave without
  it, write the reason into `NIGHT_LOG.md`, and continue — a blocked task never blocks the remaining waves.
- `NIGHT_LOG.md` gets three lines per wave: what passed, what failed and why, what the next wave starts from.

| Wave | Tasks | Check before the commit |
| --- | --- | --- |
| 1 | T1–T6 | `uv run --no-sync python -c "import apps.api.app.rag.chunk, apps.api.app.agent.tools, apps.api.app.agent.llm, apps.api.app.ingest.parsers"` plus each task's own acceptance output |
| 2 | T7–T10 | a real PDF ingests, and 50 synthetic chunks come back from both the vec0 and the FTS index |
| 3 | T11–T14 | one `/run` request streams `token` events and ends on exactly one `final` |
| 4 | T15–T17 | `docker compose config` is valid, the eval harness writes `docs/evidence/results.md`, CI parses |

---

## Wave 1 — pure modules, zero cross-imports

### T1 · rag/chunk.py

**Target** `apps/api/app/rag/chunk.py`. Nothing else.
**Change** Implement `split_pages(pages: list[dict], *, target_chars: int = 1200, overlap: int = 150) -> list[dict]`
exactly as declared in `CONTRACT.md`. Input rows are `{"page": int, "text": str}`. Split on paragraph boundaries
first (`\n\n`), then sentence boundaries, then hard-cut only when a single sentence exceeds `target_chars`. Carry
`overlap` characters from the previous chunk into the next. Skip pages whose text is blank after `strip()`. Return
rows `{"ordinal": int, "page": int | None, "text": str}` with `ordinal` contiguous from 0. Also export
`chunk_id(doc_id: str, ordinal: int) -> str` returning `f"{doc_id}:{ordinal:05d}"`.
**Acceptance**
```
uv run --no-sync python -c "
from apps.api.app.rag.chunk import split_pages, chunk_id
pages=[{'page':1,'text':'Абзац один. '*80},{'page':2,'text':'   '},{'page':3,'text':'Екінші бет. '*90}]
c=split_pages(pages)
print(len(c), [x['ordinal'] for x in c][:6], {x['page'] for x in c})
print(max(len(x['text']) for x in c), chunk_id('d',7))
assert [x['ordinal'] for x in c]==list(range(len(c))) and 2 not in {x['page'] for x in c}
"
```

### T2 · agent/tools.py

**Target** `apps/api/app/agent/tools.py`.
**Change** `Tool` dataclass (`name`, `description`, `params: type[BaseModel]`, `fn`), `ToolRegistry` with
`register/get/list` (duplicate name → `ValueError`), `to_function_schema(tool) -> dict` producing the OpenAI
function-calling shape from `tool.params.model_json_schema()`, and
`async def call_tool(registry, name, args: dict) -> dict` returning `{"ok": True, "result": ...}` or
`{"ok": False, "error": str}`. `call_tool` validates `args` through the pydantic model, awaits coroutine functions,
runs sync functions in a thread (`anyio.to_thread.run_sync`), and never raises.
**Acceptance**
```
uv run --no-sync python -c "
import asyncio, pydantic
from apps.api.app.agent.tools import Tool, ToolRegistry, to_function_schema, call_tool
class P(pydantic.BaseModel):
    q: str
    k: int = 5
r=ToolRegistry(); r.register(Tool('echo','echo back',P,lambda q,k: {'q':q,'k':k}))
print(to_function_schema(r.get('echo')))
print(asyncio.run(call_tool(r,'echo',{'q':'hi'})))
print(asyncio.run(call_tool(r,'echo',{'k':'not-an-int'})))
print(asyncio.run(call_tool(r,'missing',{})))
"
```

### T3 · agent/llm.py

**Target** `apps/api/app/agent/llm.py`.
**Change** `class LLMUnavailable(RuntimeError)`. `get_client() -> AsyncOpenAI` built from `get_settings()`
(`base_url`, `api_key`, `timeout=llm_timeout_s`), raising `LLMUnavailable` with a readable message when
`llm_configured` is false. `async def complete(messages, *, tools=None, max_tokens=None) -> dict` returning
`{"content": str, "tool_calls": list, "finish_reason": str, "usage": dict}` and
`async def stream(messages, *, tools=None, max_tokens=None) -> AsyncIterator[dict]` yielding
`{"delta": str}` / `{"tool_call": {...}}` / `{"done": {...}}`. Two guards are mandatory, both observed against this
gateway: `message.content` may be `None` on reasoning models — normalise to `""`, never dereference; and
`finish_reason == "length"` with empty content means the budget went to reasoning tokens — retry **once** with
doubled `max_tokens` capped at 4096, then give up with a clear error.
**Acceptance**
```
uv run --no-sync python -c "
import asyncio
from apps.api.app.agent.llm import complete, stream, LLMUnavailable, get_client
r=asyncio.run(complete([{'role':'user','content':'Reply with the single word READY'}], max_tokens=512))
print('content:', repr(r['content']), r['finish_reason'], r['usage'])
async def s():
    out=[]
    async for ev in stream([{'role':'user','content':'Count 1 to 3'}], max_tokens=512):
        out.append(ev)
    return out[:3], out[-1]
print(asyncio.run(s()))
"
LLM_API_KEY= uv run --no-sync python -c "
from apps.api.app.config import get_settings; get_settings.cache_clear()
from apps.api.app.agent.llm import get_client, LLMUnavailable
try: get_client()
except LLMUnavailable as e: print('degraded ok:', e)
"
```

### T4 · ingest/parsers.py

**Target** `apps/api/app/ingest/parsers.py`.
**Change** Pure parsing, no database. `parse_pdf`, `parse_docx`, `parse_xlsx`, `parse_csv`, `parse_txt`, each
`(path: Path) -> list[dict]` of `{"page": int, "text": str}`; plus `parse_any(path) -> tuple[list[dict], str]`
returning pages and the detected media type, and `supported_suffixes() -> set[str]`.
Rules: PDF text via `pypdfium2`; when a page yields under 20 characters, fall back to `pdfplumber` for that page;
if it is still empty, try `rapidocr_onnxruntime` when importable and otherwise mark the page
`"[no extractable text]"` — never crash. XLSX via `openpyxl`: unmerge merged ranges and fill the value down, one
page per sheet, rows joined as tab-separated lines (this is the stat.gov workbook shape). CSV via
`charset_normalizer` detection then `pandas.read_csv`, rendered as text. DOCX via `python-docx`, paragraphs and
tables. Unknown suffix → `ValueError` listing supported ones. PyMuPDF is banned.
**Acceptance**
```
mkdir -p data/fixtures && curl -sL -o data/fixtures/dummy.pdf https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf
uv run --no-sync python -c "
from pathlib import Path
import openpyxl, csv
from apps.api.app.ingest.parsers import parse_any, supported_suffixes
wb=openpyxl.Workbook(); ws=wb.active; ws['A1']='Регион'; ws['B1']='2025'; ws.merge_cells('A2:A3'); ws['A2']='Астана'; ws['B2']=1; ws['B3']=2
Path('data/fixtures').mkdir(parents=True, exist_ok=True); wb.save('data/fixtures/t.xlsx')
Path('data/fixtures/t.csv').write_text('a,b\n1,2\n', encoding='utf-8')
for f in ['dummy.pdf','t.xlsx','t.csv']:
    pages, mt = parse_any(Path('data/fixtures')/f)
    print(f, mt, len(pages), repr(pages[0]['text'][:60]))
print(sorted(supported_suffixes()))
"
```

### T5 · root documentation files

**Target** `.env.example`, `LICENSE`, `.dockerignore`, `README.md` at the repo root. No code.
**Change** `.env.example` lists every variable read by `apps/api/app/config.py` plus `NEXT_PUBLIC_API_BASE`, each
with a one-line comment and a safe placeholder, no real values. `LICENSE` is MIT, holder `HackAlem team`, year 2026.
`.dockerignore` excludes `.venv`, `data`, `node_modules`, `.next`, `__pycache__`, `.git`, `.env`, `*.db*`.
`README.md` is a skeleton with these H2 sections in order and a one-line instruction inside each about what will be
written there on the build day: Overview, Problem and case requirements, What it does, Architecture, Technologies,
Installation, Running the project, Dependencies and requirements, Environment parameters, How to verify the main
scenario, Data sources, Evaluation and evidence, Limitations and known gaps, Disclosure of reused code and AI
tooling, Licence. The eight sections from Installation through How to verify are mandated verbatim by the
regulation (5.4.15) and are an admission gate — a project experts cannot launch from them is dropped without
appeal. Every section stays empty of claims: no feature is described before it exists.
**Acceptance** `ls -la .env.example LICENSE .dockerignore README.md && grep -c '^## ' README.md && grep -E '^[A-Z_]+=' .env.example`

### T6 · web scaffold

**Target** `apps/web/` only.
**Change** Scaffold a Next.js app **without** `create-next-app` interactivity: write `package.json` with exact pins
`next@16.3.5`, `react@19.3.0`, `react-dom@19.3.0`, `typescript@5.9.3`, `@types/react`, `@types/node`,
`tailwindcss@4.3.3`, `@tailwindcss/postcss`, `clsx`, `lucide-react`; App Router under `src/app`; `tsconfig.json`
strict; Tailwind v4 wiring via `postcss.config.mjs` and a single `@import "tailwindcss";` in `src/app/globals.css`;
`next.config.ts` with `output: "standalone"`; `.env.local.example` with `NEXT_PUBLIC_API_BASE=http://localhost:8000`.
The page at `/` renders a placeholder shell only — the real UI is T14. Run `npm install` and `npm run build`.
**Acceptance** `cd apps/web && npm run build` — paste the build summary, including the route table.

---

## Wave 2 — storage and persistence

### T7 · rag/embed.py

**Target** `apps/api/app/rag/embed.py`.
**Change** Lazy singleton `SentenceTransformer` loaded from `settings.embed_model` on first use (module import must
stay free of model loading). `embed_texts(texts: list[str], *, batch_size: int = 32) -> numpy.ndarray` returning
float32, L2-normalised, shape `(len(texts), settings.embed_dim)`; assert the dimension and raise a clear error on
mismatch naming both numbers. `embed_query(text) -> numpy.ndarray`. `warmup() -> float` returning load seconds.
Model files download to the HF cache — that is expected; do not vendor weights.
**Acceptance**
```
uv run --no-sync python -c "
import numpy as np
from apps.api.app.rag.embed import embed_texts, warmup
print('load s:', round(warmup(),1))
v=embed_texts(['Инфляция в Казахстане выросла','Қазақстанда инфляция өсті','погода в Алматы'])
print(v.shape, v.dtype, round(float(v[0]@v[1]),3), round(float(v[0]@v[2]),3))
"
```

### T8 · rag/store.py

**Target** `apps/api/app/rag/store.py`.
**Change** Index tables against the same SQLite file: `vec_chunks` as `vec0(chunk_id TEXT PRIMARY KEY, embedding
float[<dim>])` and `chunks_fts` as FTS5 over `text` with `content='chunks'`, `content_rowid` wired to `chunks.rowid`
and the `unicode61` tokenizer with `remove_diacritics 0`. Load the extension on every connection via
`sqlite_vec.load`. Functions: `ensure_index()`, `upsert_chunks(rows: list[dict], vectors: np.ndarray) -> int`,
`knn(vector, k) -> list[tuple[str, float]]`, `bm25(query, k) -> list[tuple[str, float]]`, `index_stats() -> dict`,
`reset_index()`. Batch inserts inside one transaction.
**Acceptance**
```
uv run --no-sync python -c "
import numpy as np, time
from apps.api.app import db
from apps.api.app.rag import store
db.init_schema(); store.reset_index(); store.ensure_index()
with db.session() as c:
    c.execute(\"INSERT OR REPLACE INTO documents (id,source,created_at) VALUES ('d1','synthetic',0)\")
    rows=[{'id':f'd1:{i:05d}','doc_id':'d1','ordinal':i,'page':1,'text':f'тестовый чанк номер {i} про инфляцию'} for i in range(50)]
    c.executemany('INSERT OR REPLACE INTO chunks (id,doc_id,ordinal,page,text) VALUES (:id,:doc_id,:ordinal,:page,:text)', rows)
v=np.random.rand(50,768).astype('float32'); v/=np.linalg.norm(v,axis=1,keepdims=True)
print('upserted', store.upsert_chunks(rows, v))
t=time.perf_counter(); print('knn', store.knn(v[3],5)[:2], 'ms', round((time.perf_counter()-t)*1000,1))
print('bm25', store.bm25('инфляция',5)[:2])
print(store.index_stats())
"
```

### T9 · ingest/pipeline.py

**Target** `apps/api/app/ingest/pipeline.py`.
**Change** `ParsedDoc` dataclass and `ingest_path(path, *, source=None) -> ParsedDoc` per `CONTRACT.md`: parse via
`parsers.parse_any`, split via `rag.chunk.split_pages`, write one `documents` row (id = sha256 of file bytes,
truncated to 16 hex chars, so re-ingesting the same file replaces rather than duplicates) and its `chunks` rows in
one transaction, return the document. Also `ingest_bytes(data: bytes, filename: str, *, source=None) -> ParsedDoc`
writing to `settings.data_dir / "uploads"` first — this is what the upload endpoint calls. Indexing is **not** done
here; the caller invokes `rag.search.index_document`.
**Acceptance**
```
uv run --no-sync python -c "
from apps.api.app.ingest.pipeline import ingest_path
from apps.api.app import db
d=ingest_path('data/fixtures/dummy.pdf'); d2=ingest_path('data/fixtures/t.xlsx')
print(d.doc_id, d.media_type, len(d.pages)); print(d2.doc_id, d2.media_type)
with db.session() as c:
    print('docs', c.execute('select count(*) from documents').fetchone()[0],
          'chunks', c.execute('select count(*) from chunks').fetchone()[0])
ingest_path('data/fixtures/dummy.pdf')
with db.session() as c:
    print('after re-ingest docs', c.execute('select count(*) from documents').fetchone()[0])
"
```

### T10 · agent/trace.py

**Target** `apps/api/app/agent/trace.py`.
**Change** `TraceWriter(run_id)` with `write(event: Event) -> None` inserting into `agent_trace`
(`payload` = `json.dumps(event.data)`, `name` = `data.get("name")`) and `write_many`. Plus
`SqliteTracingProcessor` implementing the `agents.tracing.TracingProcessor` interface
(`on_trace_start/on_trace_end/on_span_start/on_span_end/shutdown/force_flush`) so SDK spans land in the same table
with `type="span"`; `install_tracing()` registers it through `agents.set_trace_processors` and is idempotent.
Writes must never raise into the caller: catch, log to stderr, continue.
**Acceptance**
```
uv run --no-sync python -c "
from apps.api.app import db
from apps.api.app.events import Event, SequenceCounter
from apps.api.app.agent.trace import TraceWriter, install_tracing
db.init_schema(); db.create_run('r1', {'prompt':'x'})
w=TraceWriter('r1'); s=SequenceCounter()
for e in [Event('status','r1',{'message':'start'},s.next()), Event('token','r1',{'text':'hi'},s.next()), Event('final','r1',{'text':'done'},s.next())]:
    w.write(e)
print(db.read_trace('r1'))
install_tracing(); install_tracing(); print('tracing installed twice, no error')
"
```

---

## Wave 3 — the vertical slice

### T11 · rag/search.py

**Target** `apps/api/app/rag/search.py`.
**Change** `Hit` dataclass and `search(query, k=10) -> list[Hit]` fusing `store.knn` and `store.bm25` with
reciprocal rank fusion (`score = Σ 1/(60 + rank)`), hydrating text/source/page by joining `chunks` and `documents`.
`index_document(doc_id) -> int` embeds that document's chunks and upserts them. `register_tools(registry)` exposes
a `search_documents` tool with a pydantic params model (`query: str`, `k: int = 5`) returning a compact list of
`{"chunk_id","source","page","text"}` — this is what the agent actually calls.
**Acceptance**
```
uv run --no-sync python -c "
from apps.api.app.rag.search import search, index_document, register_tools
from apps.api.app.agent.tools import ToolRegistry
from apps.api.app.ingest.pipeline import ingest_path
d=ingest_path('data/fixtures/dummy.pdf'); print('indexed', index_document(d.doc_id))
for h in search('dummy pdf file', 3): print(round(h.score,4), h.page, h.source, h.text[:50])
r=ToolRegistry(); register_tools(r); print([t.name for t in r.list()])
"
```

### T12 · agent/loop.py

**Target** `apps/api/app/agent/loop.py`.
**Change** `async def run_agent(prompt, *, run_id, registry, history=None) -> AsyncIterator[Event]` per contract.
Behaviour: emit `status` on start; stream assistant text as `token` events; when the model returns tool calls, emit
`tool_call`, execute through `tools.call_tool`, emit `tool_result` with elapsed ms, feed results back and continue;
hard cap of 6 model turns, after which it finishes with whatever text it has; emit `citation` for every
`search_documents` hit that appears in the final text; terminate with exactly one `final` **or** exactly one
`error`. Every event is assigned a `seq` from one `SequenceCounter` and written through `TraceWriter` before being
yielded. `db.create_run` at entry, `db.finish_run` in a `finally`. `LLMUnavailable` becomes one `error` event with
a readable message, not a traceback. Nothing in this module prints.
**Acceptance**
```
uv run --no-sync python -c "
import asyncio, uuid
from apps.api.app.agent.tools import ToolRegistry
from apps.api.app.agent.loop import run_agent
from apps.api.app.rag.search import register_tools
from apps.api.app import db
r=ToolRegistry(); register_tools(r); rid=uuid.uuid4().hex
async def go():
    seen=[]
    async for e in run_agent('Найди в загруженных документах слово dummy и процитируй строку', run_id=rid, registry=r):
        seen.append(e.type)
        if e.type in ('final','error'): print(e.type, str(e.data)[:200])
    return seen
print(asyncio.run(go()))
print('persisted events:', len(db.read_trace(rid)))
"
```

### T13 · HTTP surface

**Target** `apps/api/app/main.py`, `apps/api/app/api/routes.py`, `apps/api/app/api/schemas.py`.
**Change** App factory with a lifespan that calls `db.init_schema()`, `install_tracing()` and builds one
`ToolRegistry` with `rag.search.register_tools`, stored on `app.state`. CORS from `settings.cors_origin_list`.
Routes exactly as in `CONTRACT.md`: `GET /healthz`, `POST /run` (`StreamingResponse`,
`media_type="text/event-stream"`, headers `Cache-Control: no-cache` and `X-Accel-Buffering: no`, frames from
`event.to_sse()`), `GET /runs/{run_id}/trace`, `POST /upload` (multipart, calls `ingest_bytes` then
`index_document`, rejects unsupported suffixes with 415 and empty files with 400). One exception handler turning
anything unhandled into `{"error":{"message":...,"type":...}}` with status 500 and no stack trace in the body.
`/healthz` returns 200 even with no LLM key.
**Acceptance**
Start the server as a supervised process, never with `&` — a backgrounded shell job blocks the agent's own tool
call: `hub` `op:"start"`, `name:"kit-api"`, `application:"uv"`,
`args:["run","--no-sync","uvicorn","apps.api.app.main:app","--port","8000"]`, `ready:{"port":8000,"timeout":60}`.
Then, and only after readiness is reported:
```
curl -s localhost:8000/healthz
curl -s -F file=@data/fixtures/dummy.pdf localhost:8000/upload
curl -sN -X POST localhost:8000/run -H 'content-type: application/json' -d '{"prompt":"Что содержится в загруженном документе?"}' | head -20
```
Stop it with `hub` `op:"stop"`, `name:"kit-api"` when the output is captured.

### T14 · web UI

**Target** `apps/web/src/` only.
**Change** One page: a chat column, a run-trace timeline and an upload dropzone. It consumes `POST /run` as a
stream — `fetch` + `ReadableStream` reader parsing SSE frames, **not** `EventSource` (that cannot POST). Render
`token` deltas into the assistant bubble, `tool_call`/`tool_result` as collapsible timeline rows with their elapsed
ms, `citation` as a source chip that expands to the snippet, `error` as a visible red state. Upload posts to
`/upload` and shows the returned chunk count. Base URL from `process.env.NEXT_PUBLIC_API_BASE`. No auth, no router
beyond `/`, no component library beyond Tailwind and `lucide-react`.
**Acceptance** `npm run build` passes, and with the API running as the supervised `kit-api` process from T13, one
screenshot of a completed run showing streamed text plus at least one tool row in the timeline.

---

## Wave 4 — shipping surface

### T15 · Docker start path

**Target** `apps/api/Dockerfile`, `apps/web/Dockerfile`, `docker-compose.yml`.
**Change** API image from `python:3.12-slim` using `uv` with `--frozen` install and a non-root user; web image
multi-stage from `node:22-slim` using the standalone output. Compose runs `api` (8000) and `web` (3000), passes
`NEXT_PUBLIC_API_BASE` at build time, mounts `./data` as a named volume for the SQLite file, declares a healthcheck
on `/healthz` and makes `web` depend on `api` being healthy. Env comes from `.env` with `${VAR:-default}` so a
missing key degrades instead of failing the parse. No database service, no profiles that are not used.
**Acceptance** `docker compose up -d --build && sleep 20 && curl -s localhost:8000/healthz && curl -sI localhost:3000 | head -3 && docker compose down`

### T16 · eval harness

**Target** `eval/queries.jsonl`, `eval/run_eval.py`.
**Change** 20 hand-written retrieval queries in Kazakh and Russian against whatever is ingested, each with the
expected `doc_id` (the file is regenerated per case on the build day — ship the harness, not the answers).
`run_eval.py` runs `rag.search.search`, computes HitRate@5 and MRR@10 with `ranx`, prints a markdown table and
writes `docs/evidence/results.md` with the table, the model name, the chunk count and a UTC timestamp.
**Acceptance** `uv run --no-sync python eval/run_eval.py` — paste the table and `cat docs/evidence/results.md`.

### T17 · CI

**Target** `.github/workflows/ci.yml`.
**Change** One workflow on push and pull request: `uv sync --frozen`, import check of every module, `pytest` if
tests exist, `docker build` of the API image. Pin `actions/checkout@v4` and `astral-sh/setup-uv@v6`. No deploy
steps, no secrets.
**Acceptance** `uv run --no-sync python -c "import yaml,sys; print(list(yaml.safe_load(open('.github/workflows/ci.yml'))))"` plus a local run of the same commands.

---

## Morning checklist — operator, after the night run

1. `git log --oneline` and `NIGHT_LOG.md`: what landed per wave, what was abandoned and why.
2. Fresh shell, `cp .env.example .env`, `docker compose up -d --build`, open `localhost:3000`, upload a PDF, ask a
   question, watch the timeline. This is the judge's path.
3. Same run with `LLM_API_KEY` emptied: the app starts, `/healthz` says `llm_configured: false`, the UI shows a
   readable error instead of a spinner. Regulation 5.6.6 makes this the shipped default, not a fallback.
4. Dispatch the `judge` agent (Opus) against the tree: score it, list fixes by points recovered per minute.
5. The import commit message and the README disclosure line are decided on the build day, not tonight.
