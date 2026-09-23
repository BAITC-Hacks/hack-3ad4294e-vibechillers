#!/usr/bin/env bash
set -euo pipefail

# Save the SSE trace, then extract the verified final Report payload for scoring.
mkdir -p data
status="$(curl -sS -N -o data/demo-events.sse -w '%{http_code}' \
  -F 'before_files=@seeds/kt/v8.docx' \
  -F 'after_files=@seeds/kt/v9.docx' \
  -F 'use_llm=false' \
  http://localhost:8000/audits)"

if [[ "$status" != 2* ]]; then
  printf 'POST /audits returned HTTP %s; response saved to data/demo-events.sse\n' "$status" >&2
  exit 1
fi

uv run --no-sync python -c '
import json
from pathlib import Path

events = [
    json.loads(line[6:])
    for line in Path("data/demo-events.sse").read_text(encoding="utf-8").splitlines()
    if line.startswith("data: ")
]
finals = [event for event in events if event["type"] == "final"]
if len(finals) != 1 or any(event["type"] == "error" for event in events):
    raise SystemExit("Audit did not end with exactly one final Report; see data/demo-events.sse")
report = finals[0]["data"]["payload"]
Path("data/demo-report.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("Report", report["run_id"], "saved to data/demo-report.json")
'