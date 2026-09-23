# Night log — autonomous build run 2026-09-22 → 23

Driver: BUILD_PLAN.md executed unattended. Three lines per wave; details in the wave commits.

## Wave 1 (T1–T6) — all passed

- Passed: T1 rag/chunk.py (acceptance: 2 chunks, ordinals contiguous, blank page skipped, max 1079 chars, chunk_id d:00007); T2 agent/tools.py (schema shape, defaults applied, both error paths → ok:false, never raises); T3 agent/llm.py (live complete → 'READY'/stop/33 tok, stream deltas + done with usage, degraded path prints 'degraded ok'); T4 ingest/parsers.py (dummy.pdf/t.xlsx/t.csv parse with correct media types, DOCX + OCR fallback + unknown-suffix ValueError proven); T5 root docs (.env.example 14 vars, MIT LICENSE, .dockerignore, README 15 H2); T6 apps/web scaffold (npm run build OK, routes / and /_not-found, strict TS enforced, standalone server verified by builder).
- Failed: none. Notes: package-lock.json is not gitignored and is committed as an artifact; `next build` rewrites tsconfig jsx→react-jsx on each run (Next's own mandatory change; committed file keeps spec value where possible).
- Wave 2 starts from: wave-1 imports pass together; fixtures exist at data/fixtures/{dummy.pdf,t.xlsx,t.csv}; rag/embed.py may assume settings.embed_model=kazembed-v5, dim 768; store.py builds vec0+FTS5 on data/app.db alongside db.py's core tables.

## Wave 2 (T7–T10) — all passed

- Passed: T7 rag/embed.py (kazembed-v5 downloaded to HF cache, load 104 s incl. download; shape (3,768) float32, paraphrase sim 0.815 vs unrelated 0.356; module import stays model-free); T8 rag/store.py (vec0 float[768] + FTS5 external-content with sync triggers; upsert 50, knn d1:00003 dist 0.0, bm25 hits, re-upsert never duplicates); T9 ingest/pipeline.py (sha256[:16] doc ids, re-ingest replaces: docs stayed 2; ingest_bytes sanitises filename, writes data/uploads, same doc_id); T10 agent/trace.py (3 events persisted verbatim, install_tracing idempotent x2, SDK custom_span landed as type='span', FK/bad-event failures only print to stderr).
- Failed: none. Incident: shared scratch data/app.db went 'database disk image is malformed' under 4 concurrent builder processes hammering vec0 shadow tables; deleted (gitignored, not an artifact), rebuilt, all checks pass. Morning note: do not run multiple processes writing vec0 on the same file at once.
- Wave 3 starts from: data/app.db is fresh with dummy.pdf ingested (doc 3df79d34abbca993, 1 chunk) + 50 synthetic d1 chunks (fake random vectors) — T11 should reset_index + re-index real docs before the search acceptance; search/index_document wires T7+T8+T9; loop wires T3+T2+T10; T13 wires everything, T14 needs the T6 scaffold + T13 server.

## Wave 3 (T11–T14) — all passed

- Passed: T11 rag/search.py (RRF fusion of knn+bm25, index_document, index_all incremental, register_tools -> search_documents; acceptance: dummy hit score 0.0328 page 1 'Dummy PDF file', call_tool ok:true with 2 hits); T12 agent/loop.py (live run: status, tokens, real search_documents tool_call/tool_result, exactly one final; 27 yielded == 27 persisted; degraded path -> ['status','error'] + finish_run('error'); turn cap 6 and mid-stream error keep the exactly-one-terminal rule); T13 HTTP surface (healthz ok, upload {doc_id,chunks,pages}, /run 108-frame SSE with contiguous seq, trace replay, 415/400/422 envelopes, keyless degraded healthz+run proven); T14 web UI (npm build clean; real-browser end-to-end run captured in data/evidence/t14-run.png — streamed answer, upload card, collapsible search_documents row with ARGS/RESULT + 69 ms, 'run complete' badge; fetch+getReader SSE parser unit-tested against split frames).
- Failed: none. Integration friction logged: T12's loop.py was broken mid-wave twice (SyntaxError, then NameError 'from_flush', then awaiting a non-awaitable _Step) — T13 caught both via hub, T12 fixed in place; my own first kit-api-check failed only because T14's still-running server held port 8000. Driver re-check after everything settled: /run streamed 63 token events, exactly one final, zero errors, trace seq contiguous 1..67.
- Wave 4 starts from: whole vertical slice works over HTTP; data/app.db holds dummy.pdf + t.xlsx + t.csv indexed; run the wave-4 trio (docker, eval harness, CI) against this tree.

## Wave 4 (T15–T17) — all passed, one incident (venv wipe, restored)

- Passed: T15 docker (compose config valid; full `docker compose up -d --build` ran: api healthy on :8000 with real /healthz + in-container /run SSE streaming + /upload, web 200 on :3000 with NEXT_PUBLIC_API_BASE inlined at build; kitdata volume survived down/up incl. trace replay and the 1.1 GB HF cache; non-root uid 10001; `--extra ocr` baked, ranx deliberately out of the API image — rationale in Dockerfile comments); T16 eval harness (20 Kazakh/Russian queries, real ranx 0.3.20 path, HitRate@5 = 1.0000, MRR@10 = 0.8917 on the 53-chunk fixture corpus; docs/evidence/results.md written from the shared DB; self-sufficient on a fresh --db too; exits 2 if an expected doc_id is absent); T17 CI (.github/workflows/ci.yml parses -> ['name',True,'permissions','jobs']; backend job: uv sync --frozen + 16-module import check with LLM_API_KEY="" — driver re-ran it, OK — + guarded pytest tolerating exit 5; docker job builds apps/api/Dockerfile; pinned checkout@v4/setup-uv@v6, no deploy, no secrets).
- Failed: none. INCIDENT (root cause found, honest): builder T17's bash resolved to WSL, where a Linux `uv run` tried to recreate the Windows .venv and pruned it mid-wave (fastapi/numpy/ranx... gone). pyproject.toml + uv.lock stayed git-clean; I restored with `uv sync --frozen --extra eval --extra ocr` strictly from the untouched lock, then re-ran a 13-module full-app import regression (OK) and a post-restore T11 end-to-end (OK). All agents cleared to use Windows-native uv only. Side fix by driver: root .dockerignore `node_modules` -> `**/node_modules` (T15 found nested apps/web/node_modules was still entering the build context).
- Next: nothing — all 17 tasks landed. Final state below.

## Final summary (04:00-ish, after wave 4)

WORKS (each verified by its builder AND re-checked by the driver):
- T1–T17 complete, four commits (wave-1 f853c10, wave-2 156bf84, wave-3 2f5efbc, wave-4 this one).
- Vertical slice: upload/parse (pdf/docx/xlsx/csv/txt incl. OCR fallback) -> chunk -> embed (kazembed-v5 768d) -> vec0+FTS5 -> RRF search -> agent loop (live tool-calling, SSE) -> FastAPI /healthz /run /upload /runs/{id}/trace -> Next.js UI with streaming chat + trace timeline (browser-proven, data/evidence/t14-run.png).
- Degraded path proven at every layer: no LLM_API_KEY -> healthz llm_configured:false, /run yields exactly one readable error event (plan's morning item 3 is satisfied at the module and HTTP level).
- Shipping surface: docker compose up -d --build serves the real stack; eval harness scores the corpus (HitRate@5 1.0000 / MRR@10 0.8917, results.md committed); CI yaml valid with import + guarded-pytest + docker-build jobs.

BROKEN / FIX FIRST IN THE MORNING:
1. Fresh-clone smoke: `git clone` + `cp .env.example .env` (empty key by design) + `docker compose up -d --build` + open :3000 — T15 proved it on THIS tree; prove it once from a clean checkout, esp. that `uv sync --frozen` in-image needs no network surprises at the venue.
2. Run `uv run --no-sync python eval/run_eval.py` once after ingesting the REAL case files on build day — queries.jsonl is fixture-scoped and must be regenerated per case (that is by design, harness ships, answers don't).
3. NEVER let WSL touch .venv again: any shell on this box must invoke uv from Git-Bash/CMD (`uv run --no-sync`). Consider a `shell` hint in AGENTS.md tomorrow.
4. tsconfig.json: `next build` rewrites jsx->react-jsx each run — harmless, but re-apply spec value only if it ever breaks a typecheck.
5. README is an intentional empty skeleton (regulation 5.4.15 sections) — fill on build day; the disclosure line + import commit message are the operator's calls, per plan.
