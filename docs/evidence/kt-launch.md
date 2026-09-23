# Stage 3 — Askat delivery / launch evidence

## Final isolated integration — 2026-09-23

**Published application pin: `996512db146a045966f30335e40bed89b2a0d1a0`.** It includes backend `b392d9bd18687eb4905f296897399d0a5eb581e9`, visual delivery `93f547987720c81a5bf354264583ab46a55d5db2`, and Askat's warning-presentation correction. The native build/browser proof below was first produced at pre-rebase `085975ff934548381a9c3cfb9ece3b6d87ce1a97`. Rebase changed only ancestry: both revisions have identical `apps` tree **`74a45077c001a0e5e610367aa3392485b51eb9e6`** and `scripts` tree **`48898e01abd394acf8cffff8f76b6269dba4bb22`**. The late pull brought current capture `1b0e40d` and independent review `7c5b273`; no runtime source changed. Final documentation/evidence follows the published code pin. Historical evidence is not silently relabelled.

**Late upstream boundary:** final documentation sync also received backend commit `9d128bf`, changing parsing/alignment and `.env.example`. That later implementation is **not covered by these runtime results**. README intentionally pins the published, source-verified `996512d`; do not treat the final documentation commit's newer backend ancestry as tested. The isolated checkout was moved to `996512d`; health, web HTTP 200 and full saved organiser Report equality were rechecked there.

### Current verdict and portable proof

Native production startup, real domain-output consumption, exact-source navigation, saved reopening, full JSON and standalone HTML **pass for the exercised scenarios**. The newly received completed OpenAI run supplies separate saved execution evidence; it is not a new Askat provider call. Expert live access, PDF/XLSX semantic acceptance, Docker, OCR/scans and public hosting remain **not closed**. No quality score is inferred from counts or exact citations.

Archive: [`stage3-askat-085975f.zip`](stage3-askat-085975f.zip), **1,303,240 bytes**, SHA-256 **`80002d7937ecf02f627bbfb752053c7bd26452f8dbdc5fc897666b036948073c`**. Its 31 members contain `verification.json`, real public synthetic control Reports/reopened Reports/traces/SSE, four standalone HTML exports and seven screenshots. Organiser material is represented by a receipt and source-navigation screenshot, not duplicated full Reports. Every archived member's size/hash was verified after packing; ZIP integrity passed. Trace/SSE here are keyless server events, not a model capture.

### Pinned runtime and commands actually exercised

- Separate clone: `C:\Users\askat\AppData\Local\Temp\fla-stage3-final-0Exp0e\checkout`. Initial detached `b392d9b` checkout was clean; no working-tree overlays were copied. Main alone ran `uv sync --frozen --no-dev --no-install-project` (93 packages, exit 0), portable Node 24.21.0 `npm ci --no-audit --no-fund` (47 packages, exit 0), and `npm run build` (Next 16.3.5, TypeScript/static generation passed). Python 3.12.12; uv 0.9.21.
- The same isolated clone was then checked out at committed `085975f`, with dependencies/build cache reused and the generated `next-env.d.ts` restored before rebuilding. Production build and TypeScript passed again. Only this isolated API/web pair was stopped/restarted; the common 18764/18874 services were untouched. API binds **19764**, production web **19874**, both loopback; API key explicitly empty, CORS restricted to the web origin.
- Readiness was observed after both starts, not assumed from process creation. `/healthz`: `status: ok`, `db: ok`, `llm_configured: false`. All five saved control Reports remained exactly equal after the pinned API restart.
- At `085975f`, the README's explicit Git shell `scripts/demo.sh` with `API_BASE_URL=http://127.0.0.1:19764` exited 0. `scripts/export_report.py --report data/demo-report.json --out data/demo-report.html` exited 0. The scoped `scripts/test_export_report.py` run passed **6 tests**. No backend/eval suite or provider was invoked.
- Source custody: **4/4 organiser inputs** and **8/8 main control inputs** matched their manifests, including organiser TXT bytes. The old LF/CRLF blocker is resolved on the new backend pin; no expected hash was weakened by Askat. Full byte/hash receipts are in the archive.

### Real output and state, by run

All these runs are deterministic. The first organiser run and five control runs were captured at `b392d9b`; the last organiser run was freshly executed at `085975f`.

| Input / transport | run_id | Findings | Unit changes | Risks | Clauses / located |
| --- | --- | ---: | ---: | ---: | ---: |
| Organiser v8/v9 DOCX, initial README script | `0cbdbff65e204209ad8ac11711eb165a` | 427 | 4 | 2 | 996 / 996 |
| Control DOCX, public multipart HTTP | `1013c324df164fcb81b2838c53aae1a2` | 19 | 7 | 2 | 72 / 72 |
| Same DOCX, request agent with key absent | `d9c0227ef4b545749109b662d55669e1` | 19 | 7 | 2 | 72 / 72 |
| Control PDF, public multipart HTTP | `0497b556937546eea767caf2f507cc2f` | 20 | 8 | 1 | 102 / 102 |
| Control one-column XLSX, public multipart HTTP | `06721f05719e4f7eaad35130cdecae91` | 0 | 0 | 0 | 72 / 72 |
| Auxiliary table XLSX, production file pickers | `c7034be9cf254f91bb25f8b90d673096` | 0 | 12 | 0 | 178 / 178 |
| Organiser v8/v9 DOCX, final pinned README script | `9f844a443aa3478dbc087d71377ec330` | 427 | 4 | 2 | 996 / 996 |

`use_llm=false` reports `agent.status=not_requested`; requested-but-keyless DOCX reports `unavailable` with the original missing-key stop reason. Both have zero turns/tool calls and no investigated IDs. Control traces have four status events plus one final, or six status events plus one final for unavailable; zero `tool_call`/`tool_result`. Every captured stream has exactly one final and every saved Report reopens in full. System parsing steps are not evidence of model participation.

### Reviewer and export checks

- Real control DOCX conclusion → retained `U538fd261f400` → before-1 §1.1/а, **block 5**, exact `Отдел архивного учета (ОАУ)` highlight; conclusion → conflict `R1573e6f06e8c` → after-1 §7.4, **block 32**, exact quote. Closing the source preserved the selected table/row. PDF's same source shows **page 2**, not extracted ordinal 44. Auxiliary XLSX `Udbf2e5e483fb` opens before-1 §@t2r2u, **sheet «Функции», B2**.
- At final `085975f`, organiser conclusion F107 opened v8 §5.3.1 with exact highlight, defining parent/role context and **block 151**, separately labelled ordinal 153. Closing the source retained F107 in the selected results page.
- Final organiser downloaded JSON was **2,421,271 bytes**, SHA-256 `c2c3742918c42e40132a1e1f61371287b92b77de1dc1c99a5da0e1cc04abc9f6`, and equalled the entire saved API Report. Local import removed the server-run query, showed 427 / 4 / 2 sections, and explicitly stated that the file was not uploaded and contained no action journal. No fields were reconstructed from UI counters.
- Standalone `file://` organiser HTML had 427 finding, 4 unit-change, 2 risk, 64 unit/role and 996 source anchors; zero broken links, external resource elements or resource requests. Four public-control HTML files retained all output/conclusion IDs, complete N:M references, quotes, coordinates, warnings and agent fields. Exact linked citation counts were 243 / 243 / 239 / 114 for DOCX / unavailable DOCX / PDF / auxiliary XLSX; zero broken anchors/external resources.
- Offline DOCX split `U1b7df4635313` kept one before and two after units, including after-1 §1.1/г at block 8. Equal clause numbers in different documents retained different source anchors. Separately exported historical `f104c91` retained partial metadata (12 turns, 25 calls, 23 IDs); this was archive consumption, not new inference.
- **Own defect fixed:** already-Russian producer limitations, including “межподразделенческие риски не оценены”, were hidden behind generic diagnostic captions. `085975f` preserves their readable text and translates the two new English parser formats, while keeping every original in details. The corrected production browser displayed the limitations and matched all original warning strings; before/after screenshots are archived. No exporter change was necessary.

### Newly supplied b392d9b agent evidence

- Completed archive [`stage3-capture-b392d9b-openai.zip`](stage3-capture-b392d9b-openai.zip), SHA-256 `d11036abe169ace52b1bf9e4c3480b83df31ba2d405ae3d531a6dadd7885681d`: agent run **`9c7199f33a9f4ca3a9a47abfd65b8c6f`**, `llm_assisted` / `completed`, model `gpt-5.5-2026-04-23`, **7 turns / 22 tool calls**, 19 investigated IDs, 19 findings / 7 unit changes / 2 risks.
- Preserved partial archive [`stage3-capture-b392d9b-budget-limited.zip`](stage3-capture-b392d9b-budget-limited.zip), SHA-256 `d52753f0c406533ba1228caa4560daaa1fe93b38e5978df5198f00293869fbe9`: run **`1c3f51541f754b20925f1d50ec47ec07`**, `llm_assisted` / `partial`, **8 turns / 26 calls**, same output counts. Stop reason retains the local budget-transport 429 refusal; it is not relabelled as completed or as a new upstream request.
- Main verified all eight manifest artifact hashes in each package and full `agent.json`/`agent-reopened.json` equality. Alibi's received [independent review](kt-quality.md) confirms saved-run source-dependent F009 resolution and selected finalization, while keeping function/conclusion/format blockers. Captured provider receipts are not an independently authenticated invoice or proof of an expert-access route.
- These supplied runs, native keyless execution and browser replay are separate evidence categories. Original captures and the older `f104c91` partial remain unchanged. No provider credential or historical approval was reused by Askat.

- Final consumer proof: [`stage3-askat-final-consumers.zip`](stage3-askat-final-consumers.zip), **339,925 bytes**, SHA-256 `9bb6387c50e57361eaff0e51700948587327939e018a6864038c639e00aadcc7`; all seven members verified after packing. Contains exact method receipts, source-identity metadata, two HTML exports and two screenshots.
- Both supplied completed/partial Reports were imported locally and downloaded with full parsed-JSON equality. Completed saved-view replay intercepted **only two exact GET paths inside one browser tab**, serving archived Report/trace, not inserting the API database or executing a model. Its 53 raw events rendered 30 journal records/22 tool cards, no SDK spans, with the existing saved-journal/not-new-run disclaimer. F002 → before-1 §2.2 opened exact quote/context at block 14. Partial trace replay was not exercised; partial local import/download and HTML were.
- Both standalone HTMLs retain 19 findings / 7 unit changes / 2 risks / 72 sources; **445 internal links each**, zero broken/duplicate targets/external resources. Agent 7/22 completed versus 8/26 partial and original 429 stop reason remain distinct. Public traces have paired unique IDs 22/22 and 26/26. Completed `read_clauses` 21/22 supplies after-1 §2.6 before `resolve_alignment` 45/46; verification 47/48 precedes selected `build_report` 49/50. Only F009 status/reason/method changes against each deterministic baseline. This is observable recorded dependency, not a semantic-quality or expert-access claim.

### Current backend handoff to Batyrkhan

These are reproducible handoff records, not claims of a private message or fixes by Askat. Use the pinned isolated API above, `POST /audits` with repeated `before_files`/`after_files` and `use_llm=false`; inspect `GET /audits/{run_id}` and `/runs/{run_id}/trace`. Inputs are under `seeds/kt/eval/control/`; upload each representation separately.

1. **PDF function fragmentation:** `before.pdf` + `after.pdf`, run `0497b556937546eea767caf2f507cc2f`. After-1 §7.4/page 2 stops at `самостоятельно`; DOCX §7.4 includes the subsequent approval and no-external-agreement text. PDF has 102 extracted clauses versus DOCX's 72 and excludes 12/22 unlabelled blocks. Coordinates now exist, but they do not restore missing function boundaries.
2. **One-column XLSX function extraction:** `before.xlsx` + `after.xlsx`, run `06721f05719e4f7eaad35130cdecae91`. All 72 source clauses are `kind=other`; coverage totals 0/0, no findings/changes/risks. Warning: sheet «Приложение» lacks explicit unit/function headers and function comparison is unavailable. Keep this limitation explicit; zero risks is not a successful risk assessment.
3. **Auxiliary XLSX column semantics:** `before-table.xlsx` + `after-table.xlsx`, run `c7034be9cf254f91bb25f8b90d673096`. The source header is `Пункт | Подразделение | Функция/основание`, yet functions remain unrecognised: 178 clauses, 12 unit changes, zero findings/risks, repeated-number diagnostics. Sheet/cell sources are accessible, but the function-extraction gate is not closed.
4. **Remaining agent/semantic gates:** the completed `b392d9b` capture has now arrived and is no longer a missing-package blocker. Independent `7c5b273` review retains M2 incomplete duplication/moved lineage and M5 order/scope entries counted as functions; see its exact F003/F018, F004/F005/F006/F008 and conclusion[1]/F012 reproductions in `eval/kt/HANDOFF.md`. These are backend decisions, not frontend/export repairs. Judge-accessible live inference remains unverified; supplied completion does not authorise another provider call or replace that access gate.

Askat changed only frontend warning presentation and delivery documentation/evidence. Backend, eval/gold/seeds, manifests/locks and shared servers were not edited. Docker/Compose, OCR, hosting and new live inference were not tested.

### Confirmed visual delivery

- Production build of the visual changes passed before publication as `93f5479`. Browser checks covered 320/768/1280/1440 px, long filenames and expanded document metadata, zero-denominator accounting, warning disclosure and source navigation.
- Measured DOCX/XLSX helper text contrast was 12.74:1; active primary action 5.86:1. These measurements cover those controls, not an accessibility certification of the entire app.
- Real browser DOCX run `8ba9128fd89e410db617d54ea703e6a2` returned 457 findings, coverage 420/420 and 413/413, 37 unresolved refs. Full downloaded JSON equalled the persisted Report. The API was the earlier isolated `8b896c1` runtime; this is visual regression evidence, not a run of the new backend.
- Source F080 → v8 §3.5/а still highlighted the exact quote and retained parent/unit context. Native diagnostic disclosures retain all original warning/event text; presentation does not alter Report data. Windows activation overlay is outside the web application.

### Supplied historical agent evidence, not a new live run

The immutable `docs/evidence/stage3-capture-f104c91.zip`, published in `d98e73b`, attests core `f104c91006c8d3d6a993881823863030e70aa4af` and the public synthetic control DOCX pair. Independent handoff `7277efa` records a genuine **partial** attempt: 25 observational calls, no proposals/build_report, 23/31 exposed finding IDs, turn-limit stop, deterministic final mode and no analytic payload change from the paired baseline. Seven unit changes are source-backed in that capture. Those facts supersede “schema-only” as a description of the current code, but do not prove completion or a fresh live-agent run at `b392d9b`.

The archive records provider approval in Batyrkhan's originating session. That historical attestation is not treated as new permission for Askat to spend, copy credentials or send organiser documents. Fresh keyless runs, supplied trace replay and any subsequently authorised live run must be labelled separately. No common server is changed for this integration.

## Historical native verdict at 8b896c1 — 2026-09-23

**Archive boundary:** every section below concerns the earlier `8b896c1` runtime unless another historical revision is named. Its empty Stage 3 fields, null coordinates and TXT mismatch are superseded by the current integration above; they are retained as historical observations, not current blockers.

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
