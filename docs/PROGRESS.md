# Progress

## Stage 2 delivery checkpoint

- Revision checked: `07a1708d1410a908bacde7c8f2201d08e75431aa`; disposable clone was clean and contained the public audit routes.
- Askat delivery: added the standard-library offline Report exporter and updated README, architecture, demo, business case and launch evidence to the current contract.
- Verified: exporter compilation and HTML safety/anchor checks passed; blocked: Docker Desktop and locked runtime packages are unavailable in this environment, so no live keyless Report/browser result is claimed.
- Handoff to Batyrkhan: reproduce `docker compose up --build`, `sh scripts/demo.sh`, `GET /audits/{run_id}` and browser quote navigation; report exact output back before release.
- Independent Alibi check: all 38 challenge citations are exact substrings, but 34/38 recorded SHA-256 values do not match current file bytes; likely line-ending normalization, but provenance must be confirmed before scoring. No Alibi files were edited.

## 14:00

- Что работает сейчас: реализован вертикальный путь upload -> parse -> chunk/embed -> SQLite-поиск -> agent SSE -> Next.js UI; `/healthz` работает без ключа.
- Что изменилось за этот час: зафиксирована архитектура текущего пути и граница будущего сравнения v8/v9; строку от Batyrkhan и строку от Alibi нужно добавить после сверки с ними.
- Что дальше: проверить запуск из чистого checkout и согласовать с Batyrkhan/Alibi фактические результаты и ближайший audit-срез.
