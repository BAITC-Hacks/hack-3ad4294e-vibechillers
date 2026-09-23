# Kazakhtelecom case launch evidence

## Scope

The submitted revision exposes the keyless two-edition audit contract:
`POST /audits` streams events with a final Report payload and
`GET /audits/{run_id}` retrieves the persisted Report.

## Commands

The historical Stage 2 clone was at
`07a1708d1410a908bacde7c8f2201d08e75431aa`; cloning did not prove deployment.
The next acceptance run must pin the submitted full commit SHA explicitly.
Prerequisites are listed in README. Use a disposable machine/VM and a fresh
shell without personal credentials. The procedure below is **pending runtime
verification**, not a successful launch transcript.

```powershell
$Revision = Read-Host "Full submitted commit SHA"
$Project = "fla-check-" + [guid]::NewGuid().ToString("N")
$Checkout = Join-Path $env:TEMP $Project
git clone https://github.com/BAITC-Hacks/hack-3ad4294e-vibechillers.git $Checkout
if ($LASTEXITCODE -ne 0) { throw "Clone failed" }
Set-Location $Checkout
git checkout --detach $Revision
if ($LASTEXITCODE -ne 0) { throw "Checkout failed" }
git rev-parse HEAD
git status --porcelain
Write-Output "Disposable project: $Project; checkout: $Checkout"
Copy-Item .env.example .env
$env:LLM_API_KEY = ""
docker compose -p $Project up --build
```

Record the full revision, tool versions, commands and actual stdout/stderr.
Do not paste environment dumps, keys or credentials into evidence. An empty
`.env` key is insufficient if an inherited environment variable overrides it.
The unique `-p` name isolates containers and the named data volume; it does
not isolate host ports. Use a disposable host with ports 8000/3000 free and
inbound access blocked: the existing Compose publishes on all interfaces.
Never stop or remove the team's stack. API/UI addresses remain
`http://localhost:8000` and `http://localhost:3000`.

## Checks

In a second terminal, enter the same disposable checkout while its stack is
running. Run the complete Report equality check from README after these commands:

```powershell
Invoke-RestMethod http://localhost:8000/healthz
bash scripts/demo.sh
uv run --no-sync python scripts/export_report.py --report data/demo-report.json --out data/demo-report.html
```

Expected keyless health response includes `"status":"ok"`, `"db":"ok"`,
and `"llm_configured":false`. The demo must print one Report run ID, create
`data/demo-report.json`, and the exporter must create standalone
`data/demo-report.html`. The retrieval response must match the saved Report's
`run_id`, findings, warnings and conclusion.

After capturing evidence, stop only this disposable project from its checkout:
`docker compose -p $Project down`. Reuse the exact project name printed/stored
in the first terminal, not the default `kit` project. Do not remove team data.

## Repository evidence

The disposable clean clone in this session confirmed the public revision and
clean worktree. The actual Docker/audit launch could not be executed here:
Docker Desktop is not installed (`docker` is not available), and the local
`.venv` has no locked runtime packages after the no-install exporter check.
Therefore no live Report, browser run or Docker output is claimed by this
record. Batyrkhan owns the shared runtime blocker; reproduce with the commands
above on a machine with Docker Desktop.

The final Askat delivery is revision `14da63e`; the disposable clone check was
performed at `07a1708` before these delivery-only changes. No application or
runtime files changed between those revisions.

The source provenance for the two organizer-provided files is recorded in
[`seeds/kt/manifest.json`](../../seeds/kt/manifest.json). No API key or other
personal credential is stored here.

## Export correction verification

Local correction based on `96e41c65cd3f82429e00ac38d192d0ff08bc0b0d`
(working-tree change, not a new committed deployment revision):

- `uv run --no-sync python scripts/test_export_report.py`: one regression
  test passed. The same test against the HEAD exporter failed because a role
  with a citation present only in `Report.units` disappeared from the HTML.
- `uv run --no-sync python scripts/export_report.py --report <temporary>/report.json --out <temporary>/report.html`:
  exited successfully with `HTML report saved to ...`. Input was synthetic,
  not an API-captured v8/v9 Report.
- Chromium opened the generated HTML over `file://`. The role and its citation
  were visible; clicking the citation selected the correct included clause.
  DOM checks found zero broken internal links, zero script elements and zero
  external resource elements. The warning remained visible and the literal
  `<script>window.__injected = true</script>` did not execute.

This verifies offline export only. Docker deployment, the real audit,
persisted HTTP retrieval and the expert UI workflow are still unverified.
The revised deployment instructions are pending rehearsal on a disposable
host with Docker; they must not be counted as successful launch evidence.