# Alibi → Batyrkhan: development error brief

## Stage 3 early synthetic inputs (2026-09-23)

Ready for development: `seeds/kt/eval/control/before.txt` and `after.txt`.
These are authored synthetic documents, NOT organiser sources. Proposals in
`control/expectations.preliminary.md` are source-first and `pending_human`.
Use the pair immediately; do not wait for all gold/holdout review.

```powershell
curl.exe -N -X POST http://127.0.0.1:8000/audits -F "before_files=@seeds/kt/eval/control/before.txt" -F "after_files=@seeds/kt/eval/control/after.txt" -F "use_llm=false"
```

The pair contains explicit retained/created/renamed/split/merged units, archive-duty
loss, overlapping request registration, procurement self-review and scoped cooperation.
DOCX/PDF/XLSX representations and their hashes follow in this same control directory.
At intake core `c0658ff` still has the Stage 2 Report: no unit_changes/risks/agent fields.
Please supply the frozen Stage 3 schema and integrated core revision for controlled capture.
The current environment has no running HTTP API and lacks FastAPI/uvicorn; no live
agent quality is claimed. Provider/model, exact synthetic inputs and spend approval
must be resolved under Stage 3 §6 before inference. Holdout remains closed.

## Historical Stage 2 brief

### Stage 3 update after schema delivery

Schema `4da43907919867ce4e8579360fe5b2ff43f9a37c` is integrated. Early input commits were
rebased to `76986e3` (TXT) and `d7e0354` (all formats and 19 provisional labels).
Use `eval/kt/BATYRKHAN-CAPTURE.md` for exact DOCX hashes, real HTTP paired capture,
external-package intake and a source-only reviewer request. Batyrkhan runs inference;
Alibi independently checks the saved package. No provider setup is requested here.

Local diagnostic Reports were produced **before** this schema integration, from the
Stage 2 runtime based on `c0658ff`. They are public domain-API runs, not HTTP/agent runs;
raw Reports and manifests are in `seeds/kt/eval/results/stage3-domain-reports/` and
`stage3-local-evidence.json`. They establish these development issues:

| Issue | Source evidence / reproducible observed behavior |
|---|---|
| PDF clause fragmentation | `before.pdf` §2.2 annual archive check and `after.pdf` §7.4 own procurement review wrap across lines. Full extracted text exists; 8/29 before and 14/39 after numbered clauses differ from source because continuations become separate `other` blocks. `build_control.py --verify-inputs` records exact refs. |
| Lost cross-unit duplicate | DOCX/TXT/XLSX before §3.1 → after §§4.1,10.1 have the same all-client registration duty with no scope separation. Report emits F010 changed to §4.1 and F030 added at §10.1, missing the complete duplicate set. Confirm sources rather than hardcoding IDs. |
| Preserved transfer called content change | Explicit split/merge orders after §§2.3–2.4; four preserved duties before §§4.1,4.2,5.1,6.1 → after §§5.1,6.1,7.1,7.3 are predicted changed instead of proposed moved. Proposed statuses remain pending_human. |
| Source locations | Three independent refs have 9 format-specific expectations: DOCX blocks, PDF pages, XLSX cells. Old runtime supplies none: 0/3 per binary format; this is an old-core gap, not a measurement of schema-only commit behavior. |
| Domain outputs | Old raw Reports lack unit_changes/risks: 7 unit and 3 risk labels unassessed per format. No risk TN or accuracy is claimed. Current null/missing agent marker also means not assessed even if lists are defaulted empty. |

Unit creation/reorganisation and conflict expectations are independently source-reviewed
by separate built-in Codex reviewers, still pending human confirmation. The two existing
development annotation disputes remain open: preserved information request changed/moved;
audit-goal procedure moved/changed when §9.37's permitted delegate changes. Original
challenge bytes and historical answers are retained. No holdout answers are included.

Stage 2 source review, baseline core at `94f216c`, public deterministic API capture after freeze `07a1708`. Only development examples below. Human confirmation by Alibi is pending; treat these as source-backed diagnoses to verify, not answers to hardcode. Do not read or tune on `hold-*` rows in `challenge.jsonl`, their fixture folders, the holdout sections of `REVIEW.md` or the source-first construction in `make_mutations.py`. `split.json` records membership and exact hashes. If any held-out example informs a fix, notify Alibi so it is moved to development before claiming results.

| Class | Development example and evidence | Required behavior to investigate |
| --- | --- | --- |
| Unsupported duplicate / role context | `dev-real-shared-information`: v8 §5.3.5→v9 §5.3.6. DNM already had its own information-request duty at v8 §5.4.3, retained at v9 §5.4.3. Baseline calls the pair duplicate using the two after refs. | Distinguish pre-existing rights of separate roles from newly overlapping responsibility; cite governing §5.3/§5.4. |
| False missing from merge/generalisation | `dev-real-correspondence`: v8 §§5.6.5,5.7.3→v9 §5.6.3. `dev-real-staffing`: v8 §§5.6.7,5.7.5→v9 §5.6.5. Parents broaden separate DKKM/DNM rights to directors of departments. | Preserve all supported predecessors with the existing many-ref contract; do not call one absorbed clause lost solely because another predecessor matched first. |
| Candidate role ambiguity | Triage 003,008,010,011 compare repeated general duties across §5.3,§5.4,§5.5. A identical DNM string often has its own DNM predecessor in v8. | Include sourced role heading and avoid replacing accountable actor with a textually similar actor. Complete candidate lists are unavailable, so this does not establish candidate-recall failure. |
| Delegate vs accountable actor | `dev-delegate`: responsibility remains with the Chief Auditor while DNM is replaced by DKKM as preparer. | Change the duty/delegate context; do not silently replace the accountable actor. |
| Parent prohibition | `dev-prohibition`: identical child about signing payment documents under forbidden→required parent. | Child-text identity must not yield unchanged when parent modality reverses. |
| Split and merge | `dev-split`, `dev-merge`, `dev-real-merge`. Triage 004/005 also moves qualifiers and actions between parent/child points. | Handle compound refs without dropping one part or counting a partial match as full success. |
| Legitimate shared duty | `dev-shared-dnm`, `dev-shared-dkkm`: proposals for a plan within explicitly different areas. | Similar wording alone must not become duplicate. |
| Alias/marker evaluator boundaries | `dev-identical-inline`, `dev-identical-repeated`, `dev-multidoc`. | These primarily test scoring identity/refs. The scorer fixes are independent of alignment changes. |

Important counting correction: the reproduced Report has **16 unresolved findings covering 33 unique refs**, not 33 unresolved findings. `coverage.unresolved=33` is the ref count. Both DOCX and TXT captures reproduced that distinction. Parsed-function coverage 420/420 and 413/413 is not extraction completeness.

The initial 25 labels remain frozen regression. Development sampling rule and pool sizes are in `SELECTION.md` and `seeds/kt/eval/triage.json`. `TRIAGE-NOTES.md` records all 16 unresolved groups and the 10 selected confident findings. No real duplicate was invented to fill a class quota; three source-ambiguous cases are triaged but not asserted as semantic gold.

Integration note outside Alibi's write scope: current Git blobs for `seeds/kt/v8.txt` and `v9.txt` use LF while their checked-out bytes/manifest hashes here use CRLF. Byte-exact source validation will fail on a clone with different checkout conversion. Please coordinate source byte preservation at the root; Alibi only pins bytes under `seeds/kt/eval/` and does not weaken SHA validation.

Reproduce evaluator checks: `uv run --no-sync python eval/kt/test_score.py`; `uv run --no-sync python eval/kt/score.py --validate-labels`. Use only development with `--labels seeds/kt/eval/challenge.jsonl --partition development <report.json>`. Human review states and raw count evidence remain in the quality record. Send changed core revision/behaviour back to Alibi for a fresh, independently scored run.

Independent AI review intake (2026-09-23): development source evidence is in `seeds/kt/eval/independent-review/development.md` and `disagreements.md`. `dev-split`, `dev-merge`, and `dev-real-shared-information` have unresolved changed/moved annotation disputes; do not tune to their current status as settled gold. `dev-real-audit-goals` requires adjudication of the governing delegation context in v8/v9 §9.37. All challenge labels remain pending human confirmation. Do not use the separate holdout report, blind packets, or holdout reviewer notes for tuning. AI agreement counts are not system accuracy or human approval.

Subsequent delegated agent decision: `dev-split` and `dev-merge` now propose moved, because both actions and responsible actor are preserved while the clause grouping changes. See `results/development-adjudication.json` for versioned grounds and old/new hashes. Human source confirmation remains pending. Re-scoring the same development predictions leaves totals unchanged; this is not a new core run. The other two development context/status questions above remain open.
