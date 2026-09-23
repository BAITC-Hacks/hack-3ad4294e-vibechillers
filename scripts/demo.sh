#!/usr/bin/env bash
set -euo pipefail

# The /audits endpoint is the planned two-edition contract. Keep the raw
# response so an integration failure is inspectable instead of hidden.
mkdir -p data
status="$(curl -sS -o data/demo-report.json -w '%{http_code}' \
  -X POST http://localhost:8000/audits \
  -F 'v8=@seeds/kt/v8.docx' \
  -F 'v9=@seeds/kt/v9.docx')"

if [[ "$status" != 2* ]]; then
  printf 'POST /audits returned HTTP %s; response saved to data/demo-report.json\n' "$status" >&2
  printf 'This checkout exposes /upload and /run, but not /audits yet.\n' >&2
  exit 1
fi

printf 'Report JSON saved to data/demo-report.json (HTTP %s)\n' "$status"