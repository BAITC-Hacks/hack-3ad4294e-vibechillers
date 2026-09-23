# Alibi → Batyrkhan: development error brief

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
