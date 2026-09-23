# Progress

## Stage 3 final integration — 2026-09-23

- Confirmed: visual-only delivery `93f5479` is published; production build and browser checks at 320/768/1280/1440 passed. Real DOCX run `8ba9128fd89e410db617d54ea703e6a2` retained 457 findings and 420/420, 413/413, 37 coverage values; downloaded JSON equalled the saved API Report. The API serving that visual smoke was still the earlier `8b896c1` backend, so it is not evidence for the new producer.
- Integrated: backend `b392d9bd18687eb4905f296897399d0a5eb581e9`, including visual delivery `93f5479`, was tested in a separate native checkout. Published Askat code pin **`996512db146a045966f30335e40bed89b2a0d1a0`** is the rebased warning fix; its `apps`/`scripts` Git trees exactly equal the built/smoked `085975f`. Received `1b0e40d` adds current OpenAI/budget-limited captures; `7c5b273` adds Alibi's independent review. No common server was changed.
- Progress reconciliation: Git author timestamps are `8b896c1` 17:10:05+06:00, `877d0ed` 17:26:06+06:00, `93f5479` 18:00:59+06:00; backend `b392d9b` is 17:08:20+05:00. These are commit timestamps, not invented hourly work logs. The undated historical 14:00 entry below is not promoted to a verified checkpoint.
- Verified: isolated frozen installs, production build/TypeScript, actual API/browser and six exporter regressions. Control DOCX run `1013c324df164fcb81b2838c53aae1a2` yielded 19 findings / 7 unit_changes / 2 risks. At pre-rebase `085975f`, README demo run `9f844a443aa3478dbc087d71377ec330` yielded 427 / 4 / 2 with complete API/download JSON equality, local import, F107 exact-source navigation and standalone HTML. Five saved controls survived the API restart unchanged. Organiser 4/4 and main control 8/8 source-byte checks pass.
- Distinction: own `not_requested` and keyless `unavailable` runs have zero model tool calls. The newly supplied `b392d9b` agent run `9c7199f33a9f4ca3a9a47abfd65b8c6f` is completed/llm_assisted, 7 turns/22 calls; budget-limited `1c3f51541f754b20925f1d50ec47ec07` remains partial, 8/26. Both return 19/7/2 and match their reopened Reports; all eight capture artifact hashes per package passed. Alibi's `7c5b273` review confirms saved source-dependent execution but retains function/conclusion/format blockers. Askat makes no new provider call or expert-access claim. Historical `f104c91` remains separate.
- Backend handoff: PDF run `0497b556937546eea767caf2f507cc2f` remains fragmented; XLSX runs `06721f05719e4f7eaad35130cdecae91` and `c7034be9cf254f91bb25f8b90d673096` extract no functions despite populated coordinates. Exact reproductions are in `docs/evidence/kt-launch.md`; Askat made no backend/eval/seed/lock changes.
- Evidence: `docs/evidence/stage3-askat-085975f.zip` contains actual public control Reports/reopened/SSE/traces/HTML, screenshots and a hashed verification manifest. Final documentation/evidence follows the tested code commit; no hourly checkpoints were invented. Docker/OCR/hosting and semantic accuracy remain unverified.
- Final capture consumption: both completed/partial JSON files round-trip fully through local browser import/download; completed saved-event UI was checked with an explicitly controlled two-GET archive replay, not new execution. Both standalone HTMLs preserve all fields with 445 valid internal links each. Portable receipts/screenshots/HTML: `docs/evidence/stage3-askat-final-consumers.zip`. Partial trace replay was not exercised.
- Late sync received backend `9d128bf` after pinned verification. Its new parser/alignment changes are not covered by this evidence; README remains pinned to published `996512d`, not the final docs commit's newer backend ancestry. No result is silently promoted to a different implementation.

## Historical Stage 3 Askat delivery at 8b896c1 — 2026-09-23

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

## Финальная интеграция 23.09

- Что работает: независимый разбор Алиби подтвердил реальный агентный цикл на b392d9b; исходные Report/SSE/GET/trace, partial-попытки и UI/export evidence опубликованы без секретов. На исправленном core e1e87ba проходят 41 backend-тест.
- Что изменилось: одноколоночный XLSX разбирает нумерованные функции с координатами; PDF сохраняет однозначные переносы строк; распоряжения остаются цитируемым контекстом, а не новыми функциями; сохранённая функция при смене владельца и полная группа дублирования учитываются отдельно от межподразделенческих рисков.
- Что дальше: завершить уже запущенный контроль на неизменном e1e87ba и передать новый пакет Алиби; не переносить метрики b392d9b на новый core. Human labels остаются pending_human, PDF-неоднозначности и независимая финальная приёмка раскрываются в evidence; внешний деплой не требуется по уточнению пользователя.
