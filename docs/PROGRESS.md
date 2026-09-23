# Progress

## Stage 3 Askat delivery — 2026-09-23

- Works now: Russian reviewer workspace consumes the published Stage 3 schema; N:M unit/function/risk navigation, exact sources and Stage 2 context, explicit agent scope/status, real SSE/trace replay, complete JSON persistence/import and safe offline HTML. Missing/null fields are not assessed, never proof of no risk.
- Changed: parallel builders delivered frontend, audit flow, exporter and deployment preparation. Main integrated `4da4390` and public control bundle through `9a633fc`; implementation commit is `8b896c1`. Backend, eval/gold/seeds, root deployment and dependency manifests/locks were not edited by Askat.
- Verified: a fresh pinned clone of `8b896c15d56f0730a6c4fc3173c944d76c29dea8`, frozen installs by the sole authorised owner, production build, loopback API/browser, real DOCX run `c016312b07cd41958640dfa6d90bc003`, full API/download JSON equality, offline navigation and six exporter regressions. Control DOCX/PDF/XLSX plus auxiliary table were uploaded through the real production UI; synthetic local JSON separately checks Stage 3 consumer boundaries. Full facts and run IDs are in `docs/evidence/kt-launch.md`.
- Open external gates: tested backend still returns empty unit_changes/risks and null agent; source locations, PDF line-wrap/XLSX-table semantics and organiser TXT byte preservation need backend/seed owners. No approved live inference route was called; Docker/OCR/public deployment are not verified.
- Next: Batyrkhan integrates the genuine bounded agent/domain producer and parser fixes; rerun paired deterministic/agent control on a permitted route. These are explicit handoff dependencies, not deferred frontend screens or invented successes. This is a current checkpoint, not a backdated hourly entry.

## Stage 2 integration and Stage 3 handoff

- Works now: integrated Stage 2 context safeguards, evaluator and exporter pass 18 + 25 + 1 targeted checks; frontend typecheck exits 0. Historical DOCX/browser/fallback evidence is preserved in `docs/evidence/stage2-core.json`; no new live-model or clean-deployment run is claimed.
- Changed: pulled teammate commits through `9638f27`, restored local core/UI changes without conflicts, recorded the full official task and Stage 3 plan, and prepared three execution prompts for Astra high fast 1.5×. Stage 3 frontend ownership moves to Askat; Batyrkhan retains backend/contracts/dependencies.
- Next: deliver the bounded audit-agent, unit changes and inter-unit risks on Alibi's control bundle, then final clean launch and release acceptance. This is a current handoff record, not a backdated hourly checkpoint; missing historical hour entries require reconciliation from real history.

## Stage 2 delivery checkpoint

- Revision checked: disposable clone `07a1708d1410a908bacde7c8f2201d08e75431aa` was clean and contained the public audit routes; final Askat delivery is `14da63e`.
- Askat delivery: added the standard-library offline Report exporter and updated README, architecture, demo, business case and launch evidence to the current contract.
- Verified: exporter compilation and HTML safety/anchor checks passed; blocked: Docker Desktop and locked runtime packages are unavailable in this environment, so no live keyless Report/browser result is claimed.
- Handoff to Batyrkhan: follow the isolated, pinned-revision procedure in `docs/evidence/kt-launch.md`; run `bash scripts/demo.sh`, compare the complete saved Report with `GET /audits/{run_id}`, and exercise browser quote navigation/reopening. Return actual output before release.
- Independent Alibi source-integrity check recorded 38 exact-substring citations and 34/38 SHA-256 mismatches. Line-ending conversion is a hypothesis, not a confirmed resolution. This is not semantic review: source-sensitive per-case decisions and returned review notes are still required. Alibi's files remain unchanged.
- Review corrections: exporter now preserves unit/role citations; a regression test fails on the previous exporter and passes after the fix. Synthetic offline HTML was exercised in Chromium with working anchors and inert `<script>` text. README/launch instructions now state host prerequisites, explicit Bash, pinned checkout, unique Compose project and inherited-key precautions. Full runtime/UI acceptance and semantic label review remain open.

## 14:00

- Что работает сейчас: реализован вертикальный путь upload -> parse -> chunk/embed -> SQLite-поиск -> agent SSE -> Next.js UI; `/healthz` работает без ключа.
- Что изменилось за этот час: зафиксирована архитектура текущего пути и граница будущего сравнения v8/v9; строку от Batyrkhan и строку от Alibi нужно добавить после сверки с ними.
- Что дальше: проверить запуск из чистого checkout и согласовать с Batyrkhan/Alibi фактические результаты и ближайший audit-срез.
