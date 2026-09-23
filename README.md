# Function Lineage Auditor

Function Lineage Auditor compares the before/after editions of an internal
regulation, preserves source clauses, and returns a Report with findings,
citations, coverage, warnings and a conclusion. The supplied Kazakhtelecom
case is anonymised organiser material; see [the manifest](seeds/kt/manifest.json)
for hashes, provenance and usage restrictions.

## Installation

The main deployment path is Docker Desktop with Compose. **End-to-end launch
is not yet verified** in the Stage 2 delivery environment; see
[the launch record](docs/evidence/kt-launch.md) for the remaining acceptance gates.
No application API key is needed for the keyless audit.

Host prerequisites (these must be on PATH, not just inside the containers):
Git for Windows including Git Bash and curl, PowerShell, Docker Desktop with
Compose, [uv](https://docs.astral.sh/uv/getting-started/installation/) and
Python 3.12. Install these tools before running the commands below. Python
project packages are installed inside the API image; the host demo/export
uses only Python's standard library. Run `git --version`, `bash --version`,
`curl --version`, `uv --version`, `python --version` and
`docker compose version` to check tool availability.

```powershell
git clone https://github.com/BAITC-Hacks/hack-3ad4294e-vibechillers.git
Set-Location hack-3ad4294e-vibechillers
Copy-Item .env.example .env
$env:LLM_API_KEY = ""
docker compose up --build
```

The compose build installs the versions from `uv.lock` and the web
`package-lock.json`. Do not run `uv add`, `uv sync`, `uv lock` or `npm install`
for the judge path.

For a disposable acceptance run, use the pinned-revision and unique Compose
project procedure in the launch record instead of reusing a team's checkout
or stack. Ports 8000 and 3000 must be free; do not stop somebody else's
services to free them. Compose currently publishes these ports on all host
interfaces: use an isolated machine/network with inbound access blocked.
Do not expose the application publicly.

## Dependencies and requirements

The API requires Python 3.12 and uses FastAPI, Uvicorn, Pydantic,
python-multipart, python-docx, pypdfium2, pdfplumber, openpyxl, pandas,
charset-normalizer, SQLite/vec0 and sentence-transformers. OCR is an optional
image-PDF fallback baked into the API image. The web image uses the pinned
Next.js/React toolchain in `apps/web/package-lock.json`.

## Running the project

After Compose becomes healthy, open `http://localhost:3000`. The API is at
`http://localhost:8000`; the browser needs that host-visible URL, not the
internal Compose service name.

## Environment parameters

Copy `.env.example` to `.env`. `LLM_API_KEY` may stay empty. Other API settings
are `LLM_BASE_URL`, `LLM_MODEL`, `LLM_TIMEOUT_S`, `LLM_MAX_TOKENS`, `DB_PATH`,
`DATA_DIR`, `SEEDS_DIR`, `EMBED_MODEL`, `EMBED_DIM`, `API_HOST`, `API_PORT` and
`CORS_ORIGINS`; the web build reads `NEXT_PUBLIC_API_BASE`. Host environment
variables override `.env` during Compose interpolation: an empty key in the
file alone does not prove a keyless environment. Use a dedicated shell with
no personal credentials and explicitly clear `LLM_API_KEY` before startup.
Never store secrets in the repository.

## How to verify the main scenario

With the stack running, execute the checked-in demo:

```powershell
bash scripts/demo.sh
uv run --no-sync python scripts/export_report.py --report data/demo-report.json --out data/demo-report.html
```

The demo uploads `v8.docx` as `before_files` and `v9.docx` as `after_files` to
`POST /audits` with `use_llm=false`, extracts exactly one final Report from the
SSE stream, and saves it. The exporter is standard library only and produces a
standalone HTML file that can be opened without the application or network.
The run ID is printed by the demo. Re-read the persisted Report through the
public API and compare the complete JSON, not only its ID:

```powershell
@'
import json
from pathlib import Path
from urllib.request import urlopen

saved = json.loads(Path("data/demo-report.json").read_text(encoding="utf-8"))
with urlopen("http://localhost:8000/audits/" + saved["run_id"], timeout=30) as response:
    fetched = json.load(response)
assert fetched == saved, "Persisted Report differs"
print("Persisted Report matches:", saved["run_id"])
'@ | uv run --no-sync python -
```

This HTTP comparison still requires a live audit run; it is not recorded as
passed in the current launch evidence.

For a quick keyless health check:

```powershell
Invoke-RestMethod http://localhost:8000/healthz
```

The expected response has `status: ok`, `db: ok` and `llm_configured: false`.

## What the audit does

The deterministic path parses both editions, aligns function clauses, verifies
citations, keeps ambiguous cases as `unresolved`, and builds a cited
conclusion. `use_llm=true` enables bounded optional adjudication; an unavailable
or failing model returns the deterministic Report with a warning rather than
blocking the audit.

## Project documents

- [Task text](seeds/kt/TASK.md)
- [Stage 1 plan, shared data contract and team modules](docs/plan.md)
- [Completed Stage 2 plan and historical assignments](docs/stage-2.md)
- [Active Stage 3 plan, full-task coverage and ownership](docs/stage-3.md)
- [Stage 3 execution prompts for all three participants](docs/stage-3-prompts.md)
- [Architecture](docs/architecture.md)
- [Launch procedure and recorded limitations](docs/evidence/kt-launch.md)
- [Demo script](docs/demo.md)
- [Business case and assumptions](docs/business-case.md)
- [Development progress](docs/PROGRESS.md)

## Limitations and known gaps

`missing` means that no supported successor was found in the supplied after
set; it is not proof of organisational loss. `duplicate` and `missing`
findings require review, and unresolved cases remain visible. DOCX `page` is a
block ordinal, not a physical Word page. No separate organisation-chart input
is included. Quality results are scoped to committed evidence; historical kit
retrieval scores are not audit accuracy.

## Evaluation and evidence

Stage 1 and Stage 2 evidence is in [docs/evidence](docs/evidence), including
quality scope and the launch record. Real, synthetic and held-out evidence are
kept separate; do not infer full-document accuracy from a small labelled sample.

## Disclosure of reused code and AI tooling

The repository contains the pre-built infrastructure kit described in
`CONTRACT.md` and the project history. Audit modules extend its existing
FastAPI, SQLite, ingestion, SSE and Next.js boundaries. Team members used AI
coding assistance during the hackathon; submitted behavior remains subject to
the checked-in code, Report contract and evidence. No personal API key is
included.

## Licence

Project code is MIT; see [LICENSE](LICENSE). The organiser-provided case
material has the separate hackathon-use restriction recorded in the manifest.

## Sources and infrastructure

The case consists of editions 8 and 9 of an anonymised internal-audit regulation.
[The manifest](seeds/kt/manifest.json) records provenance, hashes and the
organiser-provided material's hackathon-use restriction.

The repository includes a pre-built infrastructure kit: document ingestion,
retrieval, agent transport, SQLite persistence and a web shell. Track-specific
audit logic is separate from that infrastructure; the kit's interfaces remain
documented in [CONTRACT.md](CONTRACT.md). Historical kit build notes and synthetic
retrieval scores are not evidence of this case's audit quality.

The repository's code licence is [MIT](LICENSE); case-material restrictions are
listed separately in the manifest.
