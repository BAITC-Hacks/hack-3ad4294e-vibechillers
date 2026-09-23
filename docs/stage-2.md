# Stage 2 — evidence-led depth and delivery

## 1. Starting point and objective

Stage 1 is complete by the team's confirmation. Do not restart it or replace its architecture.
The recorded baseline in [kt-quality.md](evidence/kt-quality.md) is 19/20 real labelled matches, 5/5 synthetic, 457 findings, 33 unresolved, and parsed-function coverage 420/420 before and 413/413 after. These are recorded Stage 1 results, not a new run or full-document accuracy. Precision is scoped to findings intersecting labelled refs; extraction completeness and unlabelled findings remain separate questions.
Goal: improve supported responsibility matching, independently measure errors outside the original sample, and make the actual audit deployable and inspectable by judges.
Requirements remain R1 comparison, R2 potential loss/duplication, R3 a source-linked conclusion from [Stage 1](plan.md#1-requirements). This plan's priorities and gates are team decisions, not organiser scoring criteria.

## 2. Architecture decisions in force

| Decision | Action and boundary |
| --- | --- |
| Keep the existing pipeline | Full-set parse → exact/lexical candidates → optional bounded LLM adjudication → verified Report → UI. No chatbot pivot or new autonomous-agent framework. |
| Prioritise sourced role context | Strengthen role-heading extraction and pass governing role/modality context into adjudication using existing `Unit`, `parent_id` and citation fields. Similar numbering is only a candidate-ranking hint, never sufficient evidence for a resolved match. |
| Preserve evidence and abstention | Raw quotes remain exact. Valid citations establish provenance, not semantic truth. Never force `real-019` or another labelled answer into code. Unresolved is preferable to an unsupported match. |
| Keep current storage and public interfaces | SQLite, existing trace/SSE, Report JSON, `POST /audits`, `GET /audits/{run_id}`. No new service, database or public status. |
| No semantic-retrieval rollout yet | First separate missing-candidate errors from wrong-decision errors. Add a retriever only through an isolated comparison if candidate recall is actually the bottleneck. |
| Keep model use optional | Keyless audit remains meaningful; model timeout/failure yields the deterministic report with warnings. Paid developer subscriptions do not grant app API access or remove keyless requirements. |

The binding data/HTTP/label contracts remain [plan.md §3](plan.md#3-contract) plus the infrastructure [CONTRACT.md](../CONTRACT.md). Batyrkhan alone integrates schema, dependency and shared-runtime changes. This document supersedes Stage 1's work assignments, not its data contracts.
Three read-only research streams inspected current core, evaluation and delivery code. The accepted findings and rejected recommendations are recorded in §7. No Stage 2 implementation or new benchmark is claimed by this planning change.

## 3. Three parallel workstreams

All three members can now use heavy AI workflows. Use them for independent implementation, adversarial review and evidence collection; never let several agents write the same files. A second agent reviews code or labels rather than rubber-stamping the first. No dependency installs or shared environment mutation from workers.

### Batyrkhan — audit semantics and integrated product

**Own:** `apps/api/app/`, `apps/web/`, shared contracts/configuration/dependencies. Existing API/UI remains the integration surface.
1. Preserve a baseline report before changing logic; consume Alibi's error categories, not held-out expected answers.
2. First core slice: improve source-backed role-heading attachment in `audit/parser.py` and governing role/modality context in `agent/audit_llm.py`. Use existing role Units and cite the actual parent heading; distinguish accountable actor from delegate rather than replacing one with the other. Preserve raw child text. Include role context in deterministic comparison only where the source supports it.
3. Prove the effect on same duty moved, nearly identical text with a changed delegate, and legitimate shared responsibility. Investigate lexical ranking only after that; never resolve a weak candidate merely because it is unique or has a nearby number. Exercise split/merge through the existing many-ref contract before proposing any shape change.
4. Ensure UI exposes source context, `review_required`, unresolved cases and model-fallback warnings. New backend semantics must be visible, not only present in JSON.
**Done:** before/after evidence for the specific failure class, independent evaluation on unchanged inputs, exact quote navigation in the actual browser, and model-unavailable completion. Report regressions, including newly confident false matches; do not claim success merely because unresolved count fell.

### Alibi — independent audit-quality workbench

**Own:** `eval/kt/`, `seeds/kt/eval/`, `docs/evidence/kt-quality.md`. Do not edit/import private alignment helpers to make the scorer agree.
1. Keep the original 25 labels as the regression set. Triage the 33 unresolved baseline findings and sample confident changed/moved/missing/duplicate findings outside the original labels; record selection criteria before inspecting new model output.
2. Build a separate human-reviewed challenge set covering owner/delegate changes, parent prohibitions, split/merge, legitimate shared duties and multi-document source aliases. AI may propose labels; final labels cite raw source and carry reviewer/disagreement information without silently changing the existing schema.
3. Reserve a source-first held-out subset before tuning; record fixture hashes and split membership in `seeds/kt/eval/split.json`. Commit the gold before the scored run in this organiser repository; core workers are instructed not to inspect/tune on that subset. This is procedural holdout, not technically blind custody. Report-derived triage examples are development data. If holdout labels influence a fix, relabel that set as development evidence.
4. Extend `eval/kt/score.py` only for demonstrated measurement gaps, keeping existing exact-set/ref semantics and the old regression results comparable. Its `clause_text` resolver currently assumes line-start unique labels; its hash-only alias mapping cannot disambiguate identical files on both sides. Add supported boundary fixtures and fail visibly on unsupported ones rather than silently excluding them. Keep semantic TP/FP/FN separate from appropriate abstention: current `unresolved` predictions are diverted before TP matching, so gold unresolved cases need a separately reported contract check, not a misleading semantic recall row.
5. Separate parsing omissions, absent candidate, wrong match, wrong status, citation failure and legitimate uncertainty; candidate recall stays unmeasured until actual candidates are captured. Reuse `make_mutations.py` and `score.py`, not a second evaluator or six new scripts. Add only necessary fixtures/checks for compound matches, aliases and false duplicate claims. Askat independently checks the disputed/source-sensitive subset and returns review notes to Alibi, who alone edits gold. Do not invent real duplicate examples if none are supported.
**Done:** resolved fixture hashes/refs/quotes, reproducible commands, raw counts and denominators, real versus synthetic versus held-out results, and an error brief for Batyrkhan. Zero-denominator metrics are N/A. Source completeness is checked against original document content, not merely against the same parser's output.
Existing entry points: `uv run --no-sync python eval/kt/score.py --validate-labels` and `uv run --no-sync python eval/kt/score.py --labels seeds/kt/eval/challenge.jsonl data/demo-report.json`. The challenge file is a Stage 2 deliverable in the existing label schema, not an already measured dataset; pass the corresponding saved reports for other fixture sets.

### Askat — executable delivery and independent judge workflow

**Own:** `scripts/`, `README.md`, `docs/architecture.md`, `docs/demo.md`, `docs/business-case.md`, `docs/evidence/kt-launch.md`, `docs/PROGRESS.md`. Root/container/configuration fixes go to Batyrkhan; no concurrent edits to `apps/**`.
1. Use the existing `scripts/demo.sh` and public HTTP/Report interface. Rehearse deployment in a disposable clean environment from a committed revision with no participant credentials; do not delete or reset anyone's working directory. Capture exact revision, commands, environment assumptions and outcomes.
2. Replace stale claims that `/audits` is absent in architecture/launch documents only with observed current behavior. Check real DOCX input, saved Report retrieval, source navigation and error presentation. A failed clean run is evidence to fix, not a reason to narrow the instructions.
3. Build `scripts/export_report.py` as a standalone Report-JSON-to-HTML exporter using the standard library. Invocation: `uv run --no-sync python scripts/export_report.py --report data/demo-report.json --out data/demo-report.html`. It must consume the public Report, preserve every finding/warning/citation, link quotes to included clauses, escape untrusted text, and work offline. No SQLite internals, external assets or new scoring logic.
4. Run the actual UI as a judge, using browser automation if available; inspect real finding → both quotes → uncertainty → reopened report. Submit reproducible UI bugs and evidence to Batyrkhan; do not change his UI files.
5. Generate the final launchable README from the actual repository, documenting installation, dependencies/env, the keyless main scenario, optional model use, limitations and third-party/pre-built disclosures. Rehearse every stated launch command; keep business time-saving numbers explicitly hypothetical unless measured.
**Done:** clean deployment and keyless audit evidence from the submitted revision, offline HTML with working quote targets, `<script>`-like source text rendered inert, reproducible browser evidence, and a README a stranger can follow without accounts. No screenshots containing secrets.

## 4. Handoffs and execution order

- Start all three streams now. Askat can use the existing Report immediately; Alibi can triage/label immediately; Batyrkhan can inspect bounded core defects without waiting for a full evaluation batch.
- Alibi first sends an error-category brief with source-backed development examples. Batyrkhan sends changed behavior and exact revision. Askat sends public-interface failures with reproduction steps. Keep these in tracked evidence, not ignored research.
- Each handoff includes owned paths, revision, exact commands, actual output and remaining limitations. Long raw runs belong in ignored `data/`; concise reproducible evidence and curated fixtures are tracked.
- Integrator runs shared validation once after merging; workers do not run project-wide suites against each other's in-flight edits. Each owner exercises their own changed behavior.
- At the next joint checkpoint, compare the same baseline/challenge inputs. Keep a change only if it fixes a supported error without introducing unsupported confident conclusions; otherwise revert that owned change, not teammates' work.
- This stage must not consume the release window: stop optional feature expansion at 17:10; reserve 17:10–18:00 for README, clean deployment, fixes and freeze. If starting later, prioritise correctness and launchability over optional depth. Hourly progress commits remain required; 18:00 is the graded state.
- Before commits: `git pull --rebase --autostash`, stage exact owned paths only, inspect the staged file list, commit and push normally. Batyrkhan coordinates shared lockfiles. Never stage another member's unfinished work.

## 5. Choices that genuinely need the team

No new infrastructure or model-provider decision blocks this stage. The conservative defaults above are executable now.
- **External model/data:** before a new provider, original-case upload, paid API use or public deployment, agree the exact provider, permitted data, spend limit and access policy. Existing developer subscriptions alone do not authorise those actions. Without that choice, use local/keyless analysis and synthetic provider checks.
- **Organisational charts:** if the organiser requires an additional chart input or export format, obtain the exact requirement/example before extending the parser. Do not fabricate a chart requirement from the brief or call a regulation-derived unit list a complete chart parser.
- **Retrieval versus richer responsibility structure:** defer until the challenge-set error categories identify the bottleneck. If both are material, present observed cases and implementation/deployment tradeoffs to the team rather than silently expanding both.

## 6. Stage 2 exit gate

- A demonstrated semantic failure class is corrected or explicitly retained as a review-required limitation; lower abstention alone is not the objective.
- Original regression and independently reviewed challenge results are published with scopes and denominators; no full-corpus accuracy claim from the initial 20 labels.
- Every supported conclusion has valid source evidence; misleading owner/delegate or duplicate claims are not hidden behind a valid quote.
- The public keyless audit, saved Report, browser citation navigation and offline export work from real inputs; optional-model failure does not destroy the report.
- Clean deployment/README evidence describes the actual submission, no closed personal credentials, and source/licence disclosures are present.

## 7. Research basis

Stage 1 evidence: [quality](evidence/kt-quality.md), [contract](plan.md#3-contract). Three scouts inspected current code without running evaluations; Main checked load-bearing recommendations against source. Previous notes under ignored `research/` are optional background, not required team instructions.

| Evidence | Accepted consequence |
| --- | --- |
| `audit/align.py` already has exact/lexical/leftover phases and owner context; the core scout found `real-019` among offered candidates | This labelled miss is not a demonstrated retrieval-recall failure. Do not extrapolate that conclusion to every unresolved case, lower thresholds to score 20/20, or hardcode the answer. |
| `audit/parser.py` role attachment is narrower than the role headings present in the case; the model prompt primarily carries clause text/unit names | First deepen sourced role/parent context, with counterexamples against overconfident reassignment. No new graph service or public fields. |
| `audit/report.py:resolve_alignment` compares cardinalities with minimums; `agent/audit_tools.py:_decision_problem` checks offered refs and evidence, not fixed 1:1 counts | Rejected the scout's claim that N:M is forbidden. Test existing support and candidate grouping before changing shape rules. |
| `agent/audit_llm.py:MAX_ADJUDICATED` is 24 and excess findings produce a warning | Keep the bound; 33 unresolved does not mean all reach the model. Do not silently increase cost or claim complete model review. |
| `eval/kt/score.py:score_group` excludes findings outside labelled refs; `clause_text` and `report_aliases` have the boundaries described above | Broaden independently reviewed evidence and make excluded/unmeasured cases explicit. Accounted parsed clauses are not proof that parsing found every duty. |
| Architecture/launch docs still describe audit as future; README is an index, while `kt-quality.md` records a live audit | Askat updates delivery to current reality and performs the clean rehearsal. Local Stage 1 success is not a clean-deployment result. |
