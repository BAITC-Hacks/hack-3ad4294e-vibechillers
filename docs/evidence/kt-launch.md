# Stage 3 — Askat delivery / launch evidence

## Verdict — 2026-09-23

**Clean native API + production browser + offline export verified at `8b896c15d56f0730a6c4fc3173c944d76c29dea8`. Full Stage 3 agent/domain acceptance is NOT closed.** The tested revision includes Batyrkhan's schema handoff `4da4390`, Alibi's public control bundle through `9a633fc`, and Askat's frontend/export implementation. Documentation-only delivery changes follow that code commit.

This is a local pinned clone, not a remote/public deployment. No provider inference, personal key, external document transfer or public exposure was used. Docker/WSL remain unavailable. No gold/holdout answers were used for these transport/reviewer checks. Observation timestamp: `2026-09-23T11:20:50.915Z`; this is a current record, not an invented hourly history.

| Gate | Observed status |
| --- | --- |
| Clean pinned native startup | PASS: frozen dependencies, production build, loopback API/web ready |
| Real organiser DOCX → SSE → persisted Report | PASS: full JSON equality; 457 findings, 996 clauses, 64 unit/role records |
| Real browser → public control DOCX/PDF/XLSX uploads | PASS for transport/display, NOT semantic accuracy |
| Conclusion/source navigation and saved reopening | PASS; exact highlight and parent/role context; unknown coordinates labelled unknown |
| JSON download/local import and offline HTML | PASS; complete Report preserved, no external assets or broken anchors |
| Stage 3 unit/risk producer and adaptive agent | OPEN: tested backend returns `unit_changes: []`, `risks: []`, `agent: null`; no model tool calls |
| Judge-accessible live-model route | OPEN: approved provider/model/input/spend/access route still required |
| All organiser source-byte hashes | FAIL for committed LF TXT; DOCX match. Control bundle 8/8 match |
| Docker, OCR/scans, public deployment | NOT TESTED |

## Environment and installation

Initial read-only probes found Git 2.49.0.windows.1; Git shell GNU Bash 5.2.37; Git curl 8.12.1; PowerShell 5.1.26100.9444; uv 0.9.21. PATH Python was 3.13, but uv-managed Python 3.12.12 was available. Docker executable/service and standard Desktop path were absent; `wsl --status` exited 50 (not installed). Bare `sh`/`bash` were not resolved by PowerShell. The initial project venv lacked application packages, and Node/npm were absent.

The user then authorised Main alone to install strictly locked dependencies and portable Node in isolated copies. No sibling installed packages; no manifests/locks were changed. Official [Node v24.21.0 Windows x64 ZIP](https://nodejs.org/dist/v24.21.0/node-v24.21.0-win-x64.zip) was checked against the official `SHASUMS256.txt`: SHA-256 `158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541`. `node --version` returned `v24.21.0`. Portable installation:

`C:\Users\askat\AppData\Local\Temp\fla-stage3-runtime-2s1VzP\node-v24.21.0-win-x64`

An earlier disposable checkout at `c0658ff7ae526adef0ccf823fe0041979767ad41` was used for integration overlays. It is **not** the clean release proof. Final release copy was created from the local repository using `git clone --no-hardlinks --no-checkout`, then `git -c core.autocrlf=false checkout --detach 8b896c15d56f0730a6c4fc3173c944d76c29dea8`. Initial `git status --porcelain` was empty. No working-tree overlays were copied into this final checkout:

`C:\Users\askat\AppData\Local\Temp\fla-stage3-release-IQKNcX\checkout`

Final `git status --porcelain` after build/browser/export showed only `M apps/web/next-env.d.ts`. Inspection confirmed Next's generated dev-to-production type paths (`.next/dev/types/{routes,root-params}.d.ts` → `.next/types/...`). Application sources and dependency manifests/locks were unchanged; no generated diff was copied back to the team checkout. “Clean pinned” describes the initial source tree, not an assertion that the build writes no generated files.

Sequential installation/build in that copy:

| Command | Actual result |
| --- | --- |
| `uv sync --frozen --no-dev --no-install-project` | Exit 0; CPython 3.12.12; 93 packages installed in 6.81 s |
| Portable `node.exe .../npm-cli.js ci --no-audit --no-fund`, cwd `apps/web` | Exit 0; 47 packages in 19 s |
| Same npm CLI `run build`, with `NEXT_PUBLIC_API_BASE=http://127.0.0.1:18764`, `NEXT_TELEMETRY_DISABLED=1`, Node on PATH | Exit 0; Next.js 16.3.5; compilation, TypeScript and static page generation passed |
| Copy `.next/static` into `.next/standalone/.next/static` | Completed; generated assets only |
| `.venv/Scripts/python.exe -m uvicorn apps.api.app.main:app --host 127.0.0.1 --port 18764` | Application startup complete; port ready |
| Portable `node.exe .next/standalone/server.js`, `HOSTNAME=127.0.0.1`, `PORT=18874` | Ready; production browser served with correct API base |

API used a fresh `data/review.db`, `DATA_DIR=data`, `CORS_ORIGINS=http://127.0.0.1:18874`, empty `LLM_API_KEY`. `/healthz` returned HTTP 200 with `status: ok`, `db: ok`, `llm_configured: false`, version 0.1.0. OCR extra was not installed. The native standalone launch retains the whole checkout/dependencies; relocating only `server.js` was not tested. [README](../../README.md) contains the reproducible native procedure. Do not replace it with an untested Docker-success claim.

## Real organiser DOCX run

In the final checkout, `API_BASE_URL=http://127.0.0.1:18764` and explicit `C:/Program Files/Git/bin/sh.exe scripts/demo.sh` exited 0:

```text
Report c016312b07cd41958640dfa6d90bc003 saved to data/demo-report.json
```

- `POST /audits` supplied `v8.docx`, `v9.docx`, `use_llm=false`; the script accepted exactly one final Report.
- `GET /audits/c016312b07cd41958640dfa6d90bc003` returned the complete same JSON, not just a matching ID.
- Report: deterministic; 457 findings; 996 clauses; 64 unit/role records; 7 warnings; function coverage 420/420 before and 413/413 after; 37 unresolved refs. Coverage is extraction accounting, not a quality percentage or full-document agent review.
- `/runs/{id}/trace`: four status events and one final, **no tool calls**. Browser reopening shows it as recorded server events, not a new agent run.
- Real production browser at `http://127.0.0.1:18874/?run=c016312b07cd41958640dfa6d90bc003` loaded the report. Conclusion F080 navigated to the later results page, highlighted `Директор направления внутреннего аудита.` in v8 §3.5/а, and exposed parent §3.5/§3 plus governing unit context. Unknown location was not replaced with ordinal-as-page.
- Full JSON download was 2,388,401 bytes; parsing it yielded exact full equality with the API Report. Its local re-import succeeded without an API upload.

Earlier working-tree integration independently exercised a browser DOCX upload (`1c044b839d3f409a894092aef04235a3`), both before/after citations for changed F003 at §1.3, and keyless fallback (`92524dbc91aa48909b0c37a253b11af1`). Those are overlay-run evidence, not final pinned runs. The earlier script Report was `fcf68af57d3345058640e31cebc04821`.

## Public synthetic control: real production-browser uploads

Source: `seeds/kt/eval/control`, received through `9a633fc`. This is Alibi's author-constructed development bundle, **not organiser data or confirmed gold**. All eight main input files matched their pinned byte counts and full SHA-256 values; equivalent representations were uploaded separately, never pooled as separate documents. No labels were used to make the frontend result.

Each row below was uploaded using the actual production file pickers and start action, then fetched from the public saved-report endpoint:

| Input pair | run_id | Clauses | Findings | Warnings |
| --- | --- | ---: | ---: | --- |
| `before.docx` / `after.docx` | `e9dc3238c35c4dc0951751cf23a8b84f` | 72 | 31 | Two unlabelled blocks per side excluded |
| `before.pdf` / `after.pdf` | `002e0dcf8acb410a85c8583ea21a682a` | 102 | 32 | 12 before / 22 after unlabelled blocks excluded |
| `before.xlsx` / `after.xlsx` (one column) | `46d918a1418948be823024309ce90b3d` | 72 | 31 | Two unlabelled blocks per side excluded |
| `before-table.xlsx` / `after-table.xlsx` (auxiliary three-column/two-sheet probe) | `827b9107091c4077949178c70f5d5a31` | 72 | 31 | Two unlabelled blocks per side excluded |

All four Reports returned zero unit_changes, zero risks and `agent: null`; all PDF/XLSX clauses had `location: null`. Frontend displays not-assessed states rather than a risk-free/complete result. Counts do not establish whether the assignments, restructuring or conflicts are correctly recognised. The PDF's extra fragments are consistent with the separately documented line-wrap ingestion defect in the control README/format QA; this run does not relabel it a successful semantic parse.

The same control DOCX pair with UI `use_llm=true`, key still absent, produced `33c73db134ff46b68e2ab92d2d203aa8`: mode deterministic, agent null, warning `LLM adjudication skipped: LLM_API_KEY is not set; the deterministic report is returned.` This proves honest keyless fallback only, not a provider, completed agent or judge-accessible inference route.

## UI boundary / failure evidence

- A real nonexistent run returned 404 and the visible Russian error `Сохранённый отчёт или журнал не найден (404). Проверьте ID запуска и адрес API.` No endless spinner.
- A malformed local JSON object was rejected as not a Report; a subsequent valid import succeeded.
- A separately labelled **synthetic local contract Report**, not an API/model result, exercised 30 findings, F30 navigation across pagination, a 1→2 N:M unit transition, R1 conflict, partial agent metadata and known sheet/cell coordinates. No tool activity was invented from synthetic counters.
- That probe rendered literal `<script>window.__stage3Injected = true</script>` inert. At 390×844, there was no page-level horizontal overflow; the risk table scrolls horizontally and its source opens as a bottom panel with exact highlighted text and `Структура / A3:C3`.
- The scoped wire smoke accepted historical Report and default-empty additions with null agent, rejected malformed/duplicate identities, reconstructed persisted events' `run_id` from the trace envelope and skipped internal SDK spans. Its mocked fetch was a consumer check, **not live-agent evidence**.
- Production browser diagnostics recorded no JavaScript exceptions. Requests aborted after terminal SSE events were visible as network diagnostics; completed Reports remained persisted/reopenable. These aborts are not evidence of server cancellation.

## Offline export / security verification

In the final pinned checkout:

```text
uv run --no-sync python scripts/test_export_report.py
Ran 6 tests ... OK
uv run --no-sync python scripts/export_report.py --report data/demo-report.json --out data/demo-report.html
HTML report saved to data\demo-report.html
```

Chromium opened the real HTML through `file://`, without API or database use: 457 finding anchors, 996 source anchors, 64 unit/role anchors, zero broken internal links and zero external assets. F080 and its source/context links were exercised visually. Null agent and default-empty additions display `Не оценивалось`.

Independent security review identified two reproducible exporter defects: duplicate source IDs could make an exact-quote link point at a different source, and wrong-edition/role-as-structural refs appeared valid. Both new regressions failed before the fix and passed afterward. Export now rejects duplicate identities and visibly annotates semantic ref mismatches without rewriting evidence. Other regressions defend role-only citations, complete Stage 3 output/context, missing versus empty data, invalid quotes and dangling references.

Synthetic Stage 3 HTML also had zero scripts/external resources/broken links; hostile markup remained literal, coordinates and risk/unit links remained accessible. This is export safety/consumer evidence, not a domain-quality result.

## Backend / runtime handoff to Batyrkhan

These are recorded handoff items, not claims of a private message or backend fix by Askat:

1. **Stage 3 producer/inference integration.** Revision `4da4390` publishes schema only. Reproduce on public control DOCX with the API above: `unit_changes=[]`, `risks=[]`, `agent=null`; trace contains only status/final. Populate genuine results/status and result-dependent tools; do not count UI contract fixtures as M1/M3 acceptance.
2. **Source coordinates.** Control PDF/XLSX runs above return `Clause.location=null` throughout. Frontend/export already accept exact page/block/sheet/cell fields; parser must provide them.
3. **XLSX table semantics.** A separate small synthetic format probe uses sheet `Responsibilities`, header `Unit | Function`, then `Purchasing department | 1.1. Purchasing department prepares orders.` versus `... prepares and approves orders.`. Overlay API run `9510d477981b4614b28b27b921d1f2c4` returned four `kind=other` clauses, no numbered function clauses/findings and no coordinates. The control auxiliary table has the marker in column A and yields findings; that does not solve a function marker inside another cell. Neither probe measures semantic accuracy.
4. **PDF line-wrap semantics.** Public control PDF run above yields 102 fragments versus DOCX's 72 and excludes 12/22 unlabelled blocks. Alibi's control README provides the independently recorded wrapped-clause defect. Preserve full function text/coordinates before claiming PDF semantic acceptance.
5. **Organiser TXT byte preservation.** Fix source preservation with the seed/runtime owner; do not weaken hashes. Details below.
6. **Live expert access.** A provider/model or tested local model-host, permitted input set, spend ceiling and access boundary need explicit agreement. Then capture paired deterministic/agent runs with genuine tools, completed/partial/failure and persisted outputs. No such route was authorised or called in this work.

Askat changed no backend, eval, gold, seeds, dependency manifests/locks or root deployment files. The UI does not patch these backend limitations with guessed outputs.

## Organiser source-byte blocker

Git system `core.autocrlf=true` made the Windows working tree match the original manifest, masking different committed TXT bytes. Final LF-preserving clone rechecked the mismatch. DOCX hashes match in both environments:

- v8.docx: 68185 bytes, `a91fb0f5e81ea323a7ff1f3a6205eb2631a487d9e7122f136f70577d0c410e98`
- v9.docx: 68480 bytes, `043853e555b8eb90b294186ee0dba33d89997827185c6be67db6fdaf3dc2a8ef`

| Source | Manifest CRLF bytes / SHA-256 | Committed and clean LF bytes / SHA-256 |
| --- | --- | --- |
| v8.txt | 155502 / `f5ce4518f22ecad2701f1fed8929d93ff09bb45af6e35e8fd60726362b6bfbc8` | 155009 / `c003195b8cedd7ea6039c1cef2b594602bb3b4ccfc8f0a242fdab7412c40c57f` |
| v9.txt | 154213 / `7ab6a7fc5396dffbcd9228149b47ed28e0c3338284ad6c2180f8acb94fdd738b` | 153721 / `f096a812a1fb95234c89d0af9ea2161e58cf0e510f1bb92bc2d4ef06243d9e17` |

493/492 CRLF sequences explain the size difference; normalising those bytes reproduced the committed hashes during initial investigation. No source/manifest/attribute fix was made by Askat. The DOCX-only demo remains byte-verified, but a claim that every organiser source passed integrity would be false.

## Historical scope

Stage 2 clone `07a1708d1410a908bacde7c8f2201d08e75431aa` and Askat delivery `14da63e` did not establish deployment: runtime packages and Docker were absent then. Its standard-library exporter and later role-only citation regression were offline synthetic checks. They remain historical evidence, not evidence of the current production browser or an adaptive agent.

The initial Stage 3 preparation worker performed read-only probes and a failing-port demo-URL check only. Positive runtime/HTTP/browser evidence above was subsequently produced by Main under the user's isolated-install approval. No historical results were silently upgraded to passed gates.
