# Progress

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
