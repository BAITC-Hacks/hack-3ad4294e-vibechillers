# Kazakhtelecom case launch evidence

## Scope

The submitted revision exposes the keyless two-edition audit contract:
`POST /audits` streams events with a final Report payload and
`GET /audits/{run_id}` retrieves the persisted Report.

## Commands

Run from the repository root after a clean clone. The Stage 2 disposable clone
was made from public `main` at revision
`07a1708d1410a908bacde7c8f2201d08e75431aa`.

```powershell
git clone https://github.com/BAITC-Hacks/hack-3ad4294e-vibechillers.git
Set-Location hack-3ad4294e-vibechillers
Copy-Item .env.example .env
docker compose up --build
```

The copied `.env` contains an empty `LLM_API_KEY`. No personal key is needed.
The compose stack publishes the API on `http://localhost:8000` and the web UI
on `http://localhost:3000`.

## Checks

In a second terminal while the stack is running:

```powershell
Invoke-RestMethod http://localhost:8000/healthz
sh scripts/demo.sh
uv run --no-sync python scripts/export_report.py --report data/demo-report.json --out data/demo-report.html
Invoke-RestMethod "http://localhost:8000/audits/<run_id>"
```

Expected keyless health response includes `"status":"ok"`, `"db":"ok"`,
and `"llm_configured":false`. The demo must print one Report run ID, create
`data/demo-report.json`, and the exporter must create standalone
`data/demo-report.html`. The retrieval response must match the saved Report's
`run_id`, findings, warnings and conclusion.

## Repository evidence

The disposable clean clone in this session confirmed the public revision and
clean worktree. The actual Docker/audit launch could not be executed here:
Docker Desktop is not installed (`docker` is not available), and the local
`.venv` has no locked runtime packages after the no-install exporter check.
Therefore no live Report, browser run or Docker output is claimed by this
record. Batyrkhan owns the shared runtime blocker; reproduce with the commands
above on a machine with Docker Desktop.

The source provenance for the two organizer-provided files is recorded in
[`seeds/kt/manifest.json`](../../seeds/kt/manifest.json). No API key or other
personal credential is stored here.