# Stage 3 evaluator labels

This extends `score.py`; it does not define an alternative product Report. The evaluator now follows Batyrkhan's frozen public `CONTRACT.md` Stage 3 amendment and `audit/models.py` at `4da43907919867ce4e8579360fe5b2ff43f9a37c`, received after the initial implementation against the Stage 3 target. This integrates the schemas only; product behavior, real inference and integrated capture remain pending. Unit IDs are source defining-clause IDs under the existing public contract, not guessed names from predictions. Freeze labels before capture.

Legacy rows omit `target` and retain all seven function statuses unchanged. New rows use `target: unit_change` or `target: risk`; reports still use `unit_changes` and `risks`. Partition/review custody remains in the existing hash-pinned `split.json` and `reviews.json`. A new label is pending human review until a human confirms it. Source-first AI proposals and AI reviewer agreement are not product accuracy or human approval.

Unit example (replace file hashes with the actual SHA-256; source files must contain the quoted numbered clauses):

```json
{
  "id": "dev-control-retained", "kind": "synthetic", "target": "unit_change",
  "documents": [
    {"doc": "before-1", "edition": "before", "file": "seeds/kt/eval/control/before.txt", "sha256": "BEFORE_SHA256"},
    {"doc": "after-1", "edition": "after", "file": "seeds/kt/eval/control/after.txt", "sha256": "AFTER_SHA256"}
  ],
  "expected_status": "retained",
  "before": [{"doc": "before-1", "unit_id": "1.1"}],
  "after": [{"doc": "after-1", "unit_id": "1.1"}],
  "unit_evidence": [
    {"doc": "before-1", "unit_id": "1.1", "name": "Отдел учета", "kind": "unit", "citations": [{"doc": "before-1", "clause_id": "1.1", "quote": "Отдел учета"}]},
    {"doc": "after-1", "unit_id": "1.1", "name": "Отдел учета", "kind": "unit", "citations": [{"doc": "after-1", "clause_id": "1.1", "quote": "Отдел учета"}]}
  ],
  "citations": [{"doc": "before-1", "clause_id": "1.1", "quote": "Отдел учета"}, {"doc": "after-1", "clause_id": "1.1", "quote": "Отдел учета"}]
}
```

Allowed unit statuses: `retained`, `reorganised`, `created`, `unresolved`. Exact before and after sets preserve edition and N:M identity. `created` requires an empty before and nonempty after; retained/reorganised require both sides. Source-backed defining unit evidence is mandatory, with `kind: unit`; risk evidence may also name `kind: role`. Evidence names must occur in defining source clauses. This is a mechanical check, not proof of correct structural interpretation or a reviewed predecessor search.

Risk rows use the same documents, citations and unit evidence, replacing expected status and before/after with:

```json
{
  "target": "risk",
  "expected_kind": "potential_conflict_of_interest",
  "refs": [{"doc": "after-1", "clause_id": "3.1"}, {"doc": "after-1", "clause_id": "3.2"}],
  "units": [{"doc": "after-1", "unit_id": "1.1"}, {"doc": "after-1", "unit_id": "1.2"}]
}
```

Both duties and defining unit/role clauses must be cited. `expected_kind` is `potential_duplication`, `potential_conflict_of_interest`, or `none`. A `none` negative expects no risk on the labelled duties; it checks both risk types and contributes to a separate negative denominator, never semantic TP. Risk precision covers predictions intersecting labelled duty refs. Unlabelled outputs are counted as unmeasured. Scope negatives narrowly enough that other legitimate risks on the same duties are not excluded. All published risks require `review_required: true`; a positive label means an advisory risk, never a proved legal breach.

Each document may add `representations: [{"file": "...docx", "sha256": "..."}, ...]`. The primary file is numbered UTF-8 source text. Every representation's raw hash is validated; document matching uses these explicit hashes plus the edition. Same bytes on different sides are disambiguated by edition; ambiguous same-side identities fail. An entry asserts that independently reviewed source text corresponds to those bytes. Hash equality alone does not prove rendering, extraction, or semantic equivalence, and scoring one format is not end-to-end evidence for another.

Optional `source_locations` entries on every label target are `{doc, clause_id, location: {page, block, sheet, cell_range}, document_sha256?}`. Only specified location keys are compared; unknown coordinates should be null. A representation-specific `document_sha256` prevents a PDF page expectation from being applied to DOCX or XLSX and must belong to that document's frozen primary/representation hashes. Empty expectation objects are rejected. Coordinates require independent source inspection. Shape checks alone do not prove physical coordinates. Both `page` and `block` are positive, 1-based integers under schema `4da4390`; zero is rejected. Location checks run even if the domain output section or agent marker is absent.

Outputs and denominators:

- Function, unit and risk groups stay separate; no pooled accuracy number.
- Missing/null `Report.agent` means **Stage 3 not assessed**, even when historical reports deserialize with default empty `unit_changes`/`risks`. These rows are excluded from semantic and negative denominators; an old default list cannot earn a correct negative. A concrete `AgentExecution` with the required `status` and `stop_reason` identifies a new producer. Its statuses include deterministic `not_requested` and requested-but-unavailable/failed; this marker alone never proves model inference or complete review. Missing/null/non-list domain sections are also unassessed. With the marker present, explicit `[]` means assessed empty output, causing FN for positive gold and correct absence for a negative. Function scoring remains independent of the agent marker.
- Exact unit `unresolved` matches contribute only to appropriate abstention. Resolvable abstentions remain FN. Risk has no explicit abstention object; absence cannot be claimed as an appropriate abstention.
- Unknown Stage 3 statuses/kinds are separate invalid-prediction FP; repeated predictions are FP after the first exact match. Every raw denominator is retained and 0/0 is N/A.
- Semantic exact-set/status agreement stays separate from Report-internal references/quotes, source-backed quotes, and source location checks. A semantic TP may still fail provenance.
- `source_backed` checks reported quotes against pinned numbered source text, including citations on new outputs. This does not measure full extraction completeness or whether the cited text entails the conclusion. Agent actions require actual trace review; no action metric is inferred from `mode` or a populated field.

Use the existing CLI, for example `python eval/kt/score.py --labels seeds/kt/eval/control/labels.jsonl --partition development REPORT.json --json-out METRICS.json`. Register the exact dataset and row hashes in the existing split first. The holdout review gate remains active. No holdout labels were consulted while implementing this extension.
