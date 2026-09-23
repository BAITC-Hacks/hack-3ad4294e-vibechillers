# Kazakhtelecom case launch evidence

## Scope

The checked-in service is the keyless document-ingestion and grounded-agent
vertical slice. It does not currently expose `POST /audits`; therefore this
record does not claim that a two-edition comparison report was produced.

## Commands

Run from the repository root after a clean clone:

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
curl.exe -s -F "file=@seeds/kt/v8.docx" http://localhost:8000/upload
curl.exe -s -F "file=@seeds/kt/v9.docx" http://localhost:8000/upload
```

Expected keyless health response includes `"status":"ok"`,
`"db":"ok"`, and `"llm_configured":false`. Each upload should return JSON
with `doc_id`, `chunks`, and `pages`; embedding model loading can make the
first upload take longer.

## Repository evidence

`NIGHT_LOG.md` records a previous full `docker compose up -d --build` smoke
test: API healthy, web returned 200, upload and `/run` SSE worked, and the
keyless path was exercised. A fresh clean-clone run for this exact Kazakhtelecom
pair still needs to be captured before the final handoff; failures should be
reported to Batyrkhan rather than hidden in this file.

The source provenance for the two organizer-provided files is recorded in
[`seeds/kt/manifest.json`](../../seeds/kt/manifest.json). No API key or other
personal credential is stored here.