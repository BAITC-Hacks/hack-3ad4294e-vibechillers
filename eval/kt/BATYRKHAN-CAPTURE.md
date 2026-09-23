# Stage 3 capture handoff — synthetic development only

Alibi prepares/evaluates; **Batyrkhan executes actual HTTP/model runs in his environment**.
No local provider/key/OMP setup is requested. Provider/model/data/spend agreement stays
with Batyrkhan under Stage 3 §6. No holdout sources or answers are needed.

## Inputs and schema handoff

Inputs commit after integration rebase: `d7e0354` (early TXT handoff `76986e3`).
Original local IDs were `8401066` / `abfc85c`; rebase onto `4da4390` rewrote them.
Use exactly one pair:

| File | SHA-256 |
|---|---|
| `seeds/kt/eval/control/before.docx` | `253413fd6a1b5c69d08959aaffd2838f83d7f1f2976fc02464b4711ba86483e5` |
| `seeds/kt/eval/control/after.docx` | `cc751b88f6b5cf5910ef6505f02a6c6bc8b7740607fa2734bcafdfd409f01b9a` |

The complete eight-file identities are in `seeds/kt/eval/control/manifest.json`.
Auxiliary real table-layout probes have their own `table-probe-manifest.json`;
they are not interchangeable with the gold-pinned single-column XLSX representation.
All inputs are author-created synthetic development data, not organiser documents.

Schema commit received: `4da43907919867ce4e8579360fe5b2ff43f9a37c` (`CONTRACT.md`).
The original core at `c0658ff` had no Stage 3 output fields. Missing fields or null/missing
`agent` are `not_assessed`, including historical Reports reserialized with empty lists.
They are never successful negative predictions. Evaluator-local label
shape is documented in `STAGE3-LABELS.md`; function gold uses the existing seven statuses.

## Capture on one integrated revision

Use a clean, pinned integrated checkout and a disposable local API process started
from that checkout, without reload or concurrent core edits. Existing project launch
instructions apply. Do not stop or replace the team's shared server. Keep the same
effective model/configuration between requests; only `use_llm` changes. Prepare:

```powershell
New-Item -ItemType Directory -Force seeds/kt/eval/data | Out-Null
python -B eval/kt/capture_control.py --prepare-attestation seeds/kt/eval/data/server-attestation.json --format docx
```

Fill the nonsecret attestation from actual runtime: schema commit, confirmation that
the server started from this exact revision, provider/model, temperature/seed (write
`unsupported` when appropriate), time/turn/tool limits and the existing approved
spend/data scope. Do not paste credentials, sensitive URLs or `.env`. The tool does
not grant inference permission or enforce provider billing. Record the actual cap
enforcement in `spend_limit_enforced_by`. Placeholders are rejected.

```powershell
python -B eval/kt/make_mutations.py --capture-control seeds/kt/eval/data/batyrkhan-stage3-docx --control-format docx --control-mode both --api-url http://127.0.0.1:8000 --server-attestation seeds/kt/eval/data/server-attestation.json
```

This calls real `POST /audits` twice, saves SSE and Report JSON, reopens each saved
Report with `GET /audits/{run_id}`, and fetches `GET /runs/{run_id}/trace`. It checks
frozen input bytes, returned document editions/hashes, stable core/revision and
saved Report equality. A failed/partial/fallback agent run stays in the evidence;
`captured` means HTTP artifacts obtained, not agent acceptance or semantic success.

Return the entire directory plus filled nonsecret attestation, actual schema/core
commit and provider/server evidence that inference occurred. If the API is hosted
elsewhere, the server revision attestation must describe that server, not an unrelated
local checkout. Do not substitute canned/replayed responses. No holdout answers.

## Independent intake by Alibi

After integrating the captured core (hash equality is required):

```powershell
python -B eval/kt/capture_control.py --verify-package seeds/kt/eval/data/batyrkhan-stage3-docx --json-out seeds/kt/eval/results/stage3-http-integrity.json
python -B eval/kt/score.py --labels seeds/kt/eval/control/labels.jsonl --partition development --json-out seeds/kt/eval/results/stage3-deterministic.json seeds/kt/eval/data/batyrkhan-stage3-docx/deterministic.json
python -B eval/kt/score.py --labels seeds/kt/eval/control/labels.jsonl --partition development --json-out seeds/kt/eval/results/stage3-agent.json seeds/kt/eval/data/batyrkhan-stage3-docx/agent.json
```

Score each mode separately; combining reports would double case evaluations. Until
Alibi confirms sources, results remain provisional agreement with `pending_human`.
Human confirmation changes require a versioned review event, not a flag added because
AI reviewers agree. Holdout capture/scoring remains closed.

Independently inspect actual ordered arguments/results: identify a returned fact and
a subsequent model-selected action that depends on it, rejected/accepted proposals,
which finding IDs were investigated, omitted scope, model turns/calls and stop reason.
Host parsing/alignment events do not prove model choice. Event counts, reported
`agent.status=completed`, or valid citations alone do not prove inference or adaptive
behavior. Keep semantic TP/FP/FN, abstention, citation provenance, coordinate checks
and action evidence separate. Report exact denominators and `N/A` for 0/0.

## Development review request without gold

For an additional independent reviewer on Batyrkhan's side, provide only
`control/before.txt`, `after.txt`, and the public §4 contract. Ask for source-backed
unit lineage, losses/overlaps, potential self-control conflicts and legitimate sharing
with complete refs and quotes. Do not provide labels, expectation prose, system
outputs or holdout. Preserve the initial response before any discussion. Existing
built-in Codex review artifacts remain AI proposals, not human gold.
