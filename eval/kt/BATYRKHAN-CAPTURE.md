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

### Final-capture intake, prepared before package delivery

No new provider calls, datasets, labels or scorer changes are needed on Alibi's
side. Evaluate only the existing synthetic **development** controls. Do not open
holdout. The `f104c91` ZIP, run IDs and `results/f104c91-independent/` remain
historical evidence for that exact core. They establish neither success nor failure
of a newer core. Do not reuse their metrics, action counts or verdict as new results.

Batyrkhan supplies the archive path and independently stated SHA-256, full core
and schema commits, two distinct new run IDs, effective nonsecret configuration
and actual execution evidence. Use the existing ZIP layout: one capture directory
with its manifest and deterministic/agent Report, reopened Report, SSE and persisted
trace; root `server-attestation.json`, `control-deterministic-score.json` and
`control-agent-score.json`. Supplemental provider/request/usage evidence, when
available, is reviewed separately. Supplied scores are comparisons, not authority.
Never reconstruct missing runtime events or replace a failed attempt with a fixture.

Fetch the stated commit normally, inspect local work, and run the **existing**
offline intake. Substitute only values actually delivered by Batyrkhan; these are
PowerShell command templates, not claims that the final package exists:

```powershell
$captureArchive = '<delivered archive path>'
$captureSha = '<independently delivered 64-character SHA-256>'
$captureCore = '<delivered full 40-character core commit>'
$captureTag = '<new core-short + agent-run-id-short>'
$captureExtract = "seeds/kt/eval/data/$captureTag"
$captureReview = "seeds/kt/eval/results/$captureTag-independent"
if ((Test-Path -LiteralPath $captureExtract) -or (Test-Path -LiteralPath $captureReview)) { throw 'Choose fresh capture paths; preserve previous evidence.' }
python -B eval/kt/review_saved_capture.py --archive $captureArchive --sha256 $captureSha --extract-to $captureExtract --output $captureReview --core-revision $captureCore
if ($LASTEXITCODE -ne 0) { throw 'Intake failed: preserve diagnostics and report the exact blocker.' }
```

The script validates ZIP custody and compares every tracked core Python file with
raw Git blobs at the **captured** revision, with no line-ending normalisation. It
checks frozen input identities, saved/reopened Reports, SSE/trace terminal payloads,
sequence and artifact hashes, attestation consistency, and captured/current frozen
scoring bytes. It then invokes existing `score.py --partition development` once
per mode and writes separate `deterministic-score.json` and `agent-score.json`.
If the delivered layout differs or the supplied scorer files are absent, record
the concrete packaging issue and request completion from Batyrkhan; do not bypass
hash checks or fabricate the missing evidence. Keep any failed intake diagnostic.

Also explicitly compare the two new run IDs against each other and the historical
IDs in the [historical capture summary](../../seeds/kt/eval/results/f104c91-independent/summary.json),
verify the schema commit resolves and its relationship to the captured core/contract,
and inspect the server-start attestation. Raw Git agreement does not prove what a remote process
loaded. Attestation, host trace and any provider evidence have distinct strength;
report absent upstream identity/usage evidence without inventing it. The script's
`full_agent_acceptance=false` and `F1_acceptance=false` are conservative defaults,
not automated semantic verdicts; final adjudication belongs in separate evidence.

### Mandatory criteria and ownership

Before delivery each criterion is **awaiting evidence**, not a failure attributed
to the new core. After intake return **passes in the evidenced scope / concrete
blocker** for each applicable criterion. No invented global accuracy threshold.
Every verdict names the core, run, source/trace event or artifact, reproduction
command, limitation and owner. Passing DOCX alone does not pass F1 or all Stage 3.

| Criterion | Required observable evidence | Blocker owner |
|---|---|---|
| C0 — custody and comparable runs | Independently supplied archive SHA; exact pinned before/after bytes and editions in both runs; same full core/schema/configuration except requested mode; complete core/artifact hashes; distinct new run IDs; Report = reopened = final SSE payload; one terminal event last, contiguous sequence and matching persisted trace. Any failed check is a named blocker before trustworthy scoring. | Batyrkhan supplies/corrects package; Alibi verifies |
| A1 — actual adaptive agent | Ordered model-selected calls and successful results; identify an actual returned fact/ref/candidate and the subsequent tool choice/arguments using it, then trace it to a validated conclusion or supported abstention/finalization. Separate host parse/align/final assembly from model choice. `completed` or tool counts alone do not pass. Record proposal attempts, guard rejections/accepted decisions, build result, investigated and omitted scope, actual stop reason and limits. An unchanged baseline can be valid only with evidenced substantive review; do not require gratuitous mutations or fewer abstentions. | Batyrkhan |
| M1 — unit lineage | Source-supported retained/created/reorganised rows on existing controls, exact before/after structural units and N:M rename/split/merge; defining and governing citations, no role promoted to unit or similarity treated as identity. Created requires an after unit plus documented predecessor search; a before-only unit without evidence of dissolution stays unresolved. Unclear identity remains explicit. | Batyrkhan |
| M2 — functions/loss | Known control deletion and preserved transfers/merges evaluated separately on frozen labels; inspect unresolved cases and source-supported reasons. Structural entries and orders must not masquerade as lost operational duties. Separate semantic TP/FP/FN, justified abstentions and unlabelled findings; disclose unresolved annotation alternatives. | Batyrkhan; Alibi owns annotation disputes |
| M3 — inter-unit risks | Both controlled duplication and potential execution/self-review conflict, with both duty sides, actor/object/scope and contextual basis. Existing legitimate-cooperation negative must not become a false risk. Empty risks alone cannot demonstrate discrimination or abstention; no legal-breach claim. | Batyrkhan |
| M4 — sources and coordinates | Resolve every published material claim to exact edition/doc/ref/quote; independently check the existing physical coordinate probes and navigability. Source-backed meaning is distinct from substring validity. Null/unsupported coordinates disclosed; missing fields mean not assessed. Review new output errors without retroactively adding labels/denominators. | Batyrkhan for Report/parser; Askat for navigation/export |
| M5 — analytical conclusion | Russian advisory conclusion links to the actual findings/unit changes/risks; no contradiction with confirmed-in-Report unit successors, no structural-clause counts called operational functions, no unsupported absence-of-risk assurance. Missing scope and next checks explicit. | Batyrkhan; Askat for presentation |
| F1 — Word/PDF/Excel | Actual DOCX plus existing PDF/XLSX control/annex evidence through supported paths, usable rows and correct physical locations. Table/diagram semantics supported by source, not inferred from successful extraction. No new dataset expansion; absent format evidence remains a named blocker. | Batyrkhan for backend/parsers; Askat for upload/navigation |
| D1 / Stage 3 exit | Saved Report and durable trace reopen; actual UI/source navigation/offline export on a pinned integrated revision; successful authorised live-agent verification route plus honest keyless/partial/failure handling and supplied guard/timeout evidence. Backend capture alone cannot establish browser, export, clean launch or expert access. | Batyrkhan for runtime/guards/access; Askat for UI/export/launch |
| Q — measurement status | Separate deterministic and agent scorer JSON, unchanged frozen development labels/reviews, raw counts and denominators by function/unit/risk, citation and coordinate checks, appropriate abstention with 0/0=N/A. Human-confirmed and pending_human remain distinct. No AI vote is human confirmation or product accuracy. | Alibi; human label confirmation by Alibi as user |

### Result-dependent trace review and final record

For each material investigation, record `result_seq/call_id → returned evidence →
next call_seq/tool/arguments → validation/result → final Report ID or abstention`.
Check exact refs/candidate IDs/offsets, temporal ordering and result availability;
similar phrasing alone is weak evidence of dependence. Include contrary evidence:
unused results, repeated pages, ignored errors, omitted refs, finalization without
substantive review. Do not infer private reasoning or turn boundaries missing from
telemetry. A pagination dependency alone does not prove an evidence-backed audit
decision. Record provider evidence actually supplied, including its limits.

Use separate source/trace reviewers where available, without gold for action review,
and **no private alignment/decision-helper calls**. Read public source/contract and
saved evidence directly. Preserve initial source judgments and disagreements;
post-capture review is not a new blind gold validation.

Keep new review under its fresh revision/run directory: integrity, two scorer
outputs, trace arguments/results review, source error brief, and a concise verdict
table `criterion | passes/blocker | evidence + reproduction | owner | scope`.
Attach a manifest of these review artifacts and keep machine JSON byte-stable under
the existing `.gitattributes` policy (write new JSON as UTF-8 LF). Update
`docs/evidence/kt-quality.md` and the acceptance index only after naming the exact
new capture; preserve the historical f104c91 section and files verbatim. Commit only
Alibi-owned paths after normal pull/rebase. No new metrics exist until the package
has actually been received and reviewed.

Score each mode separately; combining reports would double case evaluations.
Human confirmation requires an explicit human decision and versioned review event.
Existing labels remain pending until that happens; no labels are changed for intake.
Holdout capture/scoring remains closed.

## Development review request without gold

For an additional independent reviewer on Batyrkhan's side, provide only
`control/before.txt`, `after.txt`, and the public §4 contract. Ask for source-backed
unit lineage, losses/overlaps, potential self-control conflicts and legitimate sharing
with complete refs and quotes. Do not provide labels, expectation prose, system
outputs or holdout. Preserve the initial response before any discussion. Existing
built-in Codex review artifacts remain AI proposals, not human gold.
