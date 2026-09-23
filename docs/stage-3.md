# Stage 3 — complete the official AI-auditor scenario

## 1. Authority, scope and remaining stages

Stage 1 and Stage 2 are complete by team confirmation. This is the active execution plan, not a claim that Stage 3 has already been implemented. It supersedes the work assignments and scope assumptions in [Stage 1](plan.md) and [Stage 2](stage-2.md). Existing runtime contracts remain in force until Batyrkhan implements the explicit amendments below.

The [full official task](https://docs.google.com/document/d/1m-r31DH6Q__9OcN4WiP453CE6drlTTQ8Px3xi3IiVHk/edit?tab=t.0), consulted 2026-09-23, is reproduced in [the task snapshot](../seeds/kt/TASK.md). The earlier four-line brief omitted mandatory unit-change classification and potential conflicts of interest. The full task also names Word, PDF and Excel. These are requirements to complete, not optional expansion. The task requires an AI-agent prototype but does not prescribe ReAct, a multi-agent framework, a model vendor or an accuracy threshold; one bounded tool-using auditor is our implementation choice.

There are **four team stages in total**, not four organiser stages:

| Stage | Status / exit |
| --- | --- |
| 1 — working audit foundation | Completed: before/after extraction, matching, cited Report, API/UI and initial evaluation. |
| 2 — context, independent measurement and delivery assets | Completed: sourced role/parent safeguards, larger evaluation workbench, offline export and delivery instructions; limitations remain explicit below. |
| 3 — full-task AI-auditor scenario | Now: integrate Stage 2, wire adaptive investigation, unit lineage, inter-unit risks and all three input-format families into one user flow. |
| 4 — release acceptance and freeze | Last: run the integrated revision as an expert, finish launch/README evidence, resolve release blockers and freeze. No planned Stage 5 during the competition. |

Stage 4 is not another feature round. Prepare its deployment path in parallel with Stage 3. Preserve the 17:10–18:00 release window and the 18:00 graded-state deadline; if work reaches that window, stop optional expansion and prioritise mandatory defects. A missing mandatory feature is a disclosed gap, not silently reclassified as optional. Hourly commits and three-line progress entries remain required.

### Execution order and scope protection

1. Integrate and commit Stage 2; freeze the §4 backend schemas before consumers diverge. Resolve the authorised model/judge-access route early, while local work continues independently.
2. Start three heavy main sessions concurrently: Batyrkhan builds the bounded audit agent and mandatory domain outputs; Alibi immediately commits a clearly labelled synthetic §11 control bundle (reorganisation, lost duty, duplicated duty, plus a conflict/control negative); Askat takes the frontend and prepares deployment. Inputs can be used for development before gold review is complete, but unapproved expectations cannot be published as confirmed accuracy.
3. Wire M1 unit changes and M3 cross-unit risks through API, UI, evaluator and export; expose XLSX upload and exercise existing DOCX/PDF/XLSX parsers on the control inputs. Do not postpone the literal §11 scenario behind optional evaluation expansion.
4. Exercise live inference with approved inputs, then hand one integrated revision to Stage 4. First defer only optional depth: extra holdout runs, cosmetic export variants, advanced cell highlighting and arbitrary diagram-layout support. Never cut exact source traceability, required formats, unit classification, potential conflicts, or launchability without the user's explicit scope decision.

All three participants use **GPT-6 Astra / high / fast 1.5×** for their main sessions (user choice). This does not select the application's inference model or automatically change subagent routing. Execution prompts are in [stage-3-prompts.md](stage-3-prompts.md). Stage 3 changes ownership: **Askat now owns `apps/web/`**, except dependency manifests/lockfiles coordinated by Batyrkhan; Batyrkhan does not edit frontend implementation concurrently.

## 2. What Stage 2 actually delivered

At initial planning, local `main` was eight commits behind `origin/main` (`9638f27`) and Batyrkhan's Stage 2 core/UI changes were uncommitted. Before the handoff commit, `git pull --rebase --autostash` integrated all eight commits and restored local changes without conflicts. Targeted integration checks passed: 18 context tests, 25 evaluator tests, one exporter regression and frontend typecheck. Historical HTTP/browser/model-failure evidence is preserved in [stage2-core.json](evidence/stage2-core.json); it is not a new live-agent or clean-deployment run.

| Owner | Delivered | Evidence and limits |
| --- | --- | --- |
| Batyrkhan | Role-heading attachment; governing parent/modality/delegate context; exact context citations and guarded LLM proposals; UI navigation to contextual sources. | [Tracked Stage 2 core record](evidence/stage2-core.json) preserves the real DOCX HTTP/SSE + saved Report retrieval, browser checks, local timeout fallback and original 19/20 real + 5/5 synthetic result. Successful external-model adjudication was not exercised. |
| Alibi | Frozen 25-row regression; 30 challenge proposals (22 development, 8 holdout); source triage, scorer boundary fixes, versioned independent AI review and error handoff. | Published quality record at `9638f27`: development draft agreement 6/12 real and 6/10 synthetic, with false positives and abstentions disclosed. Human confirmation is pending; holdout was not scored. These measurements used the earlier core and are not measurements of Batyrkhan's new local changes or of an agent. |
| Askat | Standalone escaped HTML exporter with role-only citations preserved; regression/browser export evidence; expanded README, architecture, business case, demo and deployment procedure. | Delivery at `a374e30`; launch record explicitly distinguishes verified synthetic offline export from unexecuted Docker/audit clean-deployment instructions. Docker was unavailable in that delivery environment. |

Counting correction: Stage 1 had **16 unresolved findings / 33 distinct refs**, not 33 unresolved findings. Batyrkhan's final Stage 2 record has **18 unresolved findings / 37 refs**; two same-ref pairs moved from unchanged to review because governing wording changed from required action to possible action. Parsed-function coverage remains 420/420 before and 413/413 after; 457 findings. More warranted abstention is not a regression merely because the count rises. Coverage and valid quotes are not semantic accuracy.

The wired `api/audits.py` still calls `audit_llm.adjudicate_report`, a fixed two-phase model pass. `agent/loop.py` already has a generic model/tool loop, but its search-hit citations and text-only final payload do not yet implement this audit workflow. Do not describe Stage 2 as a measured autonomous-agent run. Preserve its useful code, rather than restarting the product.

Reuse the existing structural matching in `audit/align.py:_unit_rows`: it already identifies explicit same-name structure entries and emits added/missing/moved/unchanged findings. The missing M1 piece is the evidenced retained/reorganised/created unit-level result, including aliases and compound transitions, not extraction from scratch. Loop reuse alone does not require a new Report schema; the unit/risk outputs below are required by the fuller domain task.

The handoff commit integrates the known teammate commits and local core changes. At each new session, inspect current work before pulling further updates; use `git pull --rebase --autostash` with normal conflict handling, never overwrite local work or broadly stage another participant's unfinished changes. Record resulting core/eval revisions. Core developers use Alibi's development-only handoff; do not open holdout answers to tune implementation.

## 3. Full-task acceptance and actual rubric

M1–M5 correspond exactly to official §7; F1 and D1 come from §§5/9/10. They replace the old short brief as the coverage checklist, without renaming the existing Finding statuses.

| Requirement | Stage 3 deliverable | Observable acceptance |
| --- | --- | --- |
| M1 — reorganised / retained / created units from annexes | Source-backed unit-lineage table with before/after units, including rename, split/merge and uncertain identity. | A controlled annex example identifies a retained, created and reorganised unit; every row opens the defining source. Listing extracted units alone does not pass. |
| M2 — function comparison and potential loss | Existing full-set matching plus agent investigation of suspected missing successors, ownership changes and compound matches. | Known deletion is flagged; a transfer/renumbering and a supported merge are not mislabeled as loss. Agent may abstain but cannot assert an unsupported loss. |
| M3 — inter-unit duplication AND potential conflicts of interest | Compare duties across units in the after set, not just before-versus-after text. Add a separately typed potential-conflict output. | Detect a controlled overlap and a supported execution/control incompatibility; distinguish legitimate shared responsibility and same wording under different scope. Cite both duties and the source basis for incompatibility. |
| M4 — source for each conclusion | Exact quotes plus resolving document/clause and, for tabular inputs, source location. | All published unit changes, function findings, risks and conclusion items resolve; arbitrary refs, unrelated parents and invented quotes are rejected. |
| M5 — understandable analytical conclusion | Russian user-facing summary covering units, lost/overlapping duties, potential conflicts, limitations and next checks. | A reviewer can traverse conclusion → finding/risk/unit change → original evidence; recommendation is explicitly advisory. |
| F1 — Word, PDF, Excel | Exercise existing DOCX/PDF/XLSX extraction end-to-end; complete upload and organisational-table interpretation where absent. | Real DOCX plus controlled PDF/XLSX annexes produce usable rows and navigable sources. Extraction success alone is not semantic support for an org chart. |
| D1 — prototype, UI, repo, README and advisory constraint | One public audit flow, saved Report, trace, offline export, launch instructions and responsible-human review warning. | Live agent mode and keyless fallback are distinguishable; all outputs remain inspectable after reopening/export. |

| Official criterion | Points | Evidence to prepare |
| --- | ---: | --- |
| Compliance and functionality | 25 | M1–M5 and F1/D1 through the actual UI on the control bundle. |
| Technical implementation | 25 | Real result-dependent tool selection, validators, bounded execution, honest partial/failure states and coherent code-to-architecture mapping. |
| README and reproducibility | 25 | Exact final-revision launch rehearsal and judge-accessible agent verification; all dependencies/env/data/disclosures documented. |
| Value and applicability | 15 | Employee workflow, interpretable risks, cited evidence, human decision boundary; no fabricated time savings. |
| Development potential and originality | 10 | Explain source-backed responsibility lineage and separation-of-duties checks; future expansion is clearly distinguished from implemented behavior. |
| Total | 100 | These are rubric weights, not points we claim to have earned. |

Defer external regulatory compliance, comparisons with other operators and optimisation/reallocation of functions (§8). Provide brief evidence-backed next checks in the conclusion; do not confuse that with a full redistribution engine. No new database, vector service, multi-agent debate or model training.

## 4. Implementation contract — Batyrkhan integrates first

### Stable interfaces and necessary report additions

Keep FastAPI, SQLite, the typed tool registry, existing `POST /audits` multipart fields including `use_llm`, `GET /audits/{run_id}`, durable trace and the existing SSE envelope. Keep the seven Finding statuses, exact-ref semantics, `Citation={doc, clause_id, quote}` and `Report.mode=deterministic|llm_assisted`. A conflict is not a new function-match status.

Before parallel builders edit consumers, Batyrkhan lands the following typed additions in `audit/models.py` and the shared contract, then communicates that revision. These shapes are the Stage 3 target, not fields present in Stage 2:

```text
UnitRef = {doc: string, unit_id: string}
SourceLocation = {page: integer|null, block: integer|null,
  sheet: string|null, cell_range: string|null}
Clause.location: SourceLocation|null
UnitChange = {id: string, status: retained|reorganised|created|unresolved,
  before: UnitRef[], after: UnitRef[], citations: Citation[], reason: string,
  method: exact|lexical|llm|human, review_required: boolean}
Risk = {id: string, kind: potential_duplication|potential_conflict_of_interest, units: UnitRef[],
  refs: ClauseRef[], citations: Citation[], reason: string,
  method: exact|lexical|llm|human, review_required: true}
Report.unit_changes: UnitChange[]
Report.risks: Risk[]
ConclusionItem.unit_change_ids: string[]
ConclusionItem.risk_ids: string[]
Report.agent = {status: not_requested|completed|partial|unavailable|failed,
  model: string|null, turns: integer, tool_calls: integer,
  investigated_finding_ids: string[], stop_reason: string}
```

Old stored Reports may omit these additions and must remain readable; absence means not assessed, never "no conflicts". New producers populate them explicitly. Update API validation, TS consumers, export and evaluator in one coordinated cutover, not an alternative Report format. Historical empty additions are not proof of new functionality.

Unit-change refs must resolve to the correct before/after edition and to actual structural units, not silently promote a mentioned role to a department. Retained requires supported identity; reorganised needs cited change evidence (rename/split/merge may be N:M); created needs an after unit plus reviewed predecessor search. A before-only unit without proof of dissolution remains unresolved. Abbreviation/string similarity alone does not prove identity. Risks may cite actual units or roles and must relate duties in the same after set. Execution plus review of one's own work can support an advisory potential-conflict inference from the cited duties; it is not proof of misconduct or a legal breach. Ordinary cooperation or the mere word "control" is insufficient. Never invent a legal separation rule; if the duties/actor relationship are unclear, abstain.

Keep existing before/after duplicate Findings; use `Risk.kind=potential_duplication` for cross-unit overlap that has no predecessor, rather than fabricating a before ref to satisfy the old duplicate shape. Link equivalent evidence in the UI and do not double-count the same risk. SourceLocation fields describe real physical PDF pages, DOCX block ordinals or workbook sheet/cell ranges; unknown coordinates remain null. Quotes still resolve through the existing ClauseRef and exact text.

### One real agent, reusing the existing engine

Reuse/refactor the conversation state machine in `agent/loop.py` and the existing LLM adapter and registry. Do not start a second framework, nest two trace writers, or return a generic text-only final in place of Report. `api/audits.py` remains the owner of audit event sequence, persistence and exactly one terminal event. Preserve unrelated `/run` behavior while separating its search-hit citation policy from audit clause-citation validation. Generalise only the narrow prompt/tool/finalisation boundary needed for both callers.

Audit tools must support: reading complete source clauses with governing context; searching alternative counterpart duties/units within this run; inspecting current findings; proposing validated unit changes and risks; resolving alignments; verifying citations; building the final Report. Use existing `parse_regulations`, `align_functions`, `resolve_alignment`, `verify_citations`, `build_report` wherever they already implement the operation. Expose typed read/search operations through the same registry, not unrestricted filesystem/network tools.

Parsing and initial alignment run once under the host's control before model investigation. Do not expose their current reset-capable implementations for arbitrary model re-execution: `parse_regulations` clears findings and `align_functions` replaces them. The investigation registry exposes read/search plus guarded proposal/verification/finalisation operations over that established run state.

Search results are evidence candidates, not accepted matches. If additional refs are needed, explicitly offer validated run-local candidates before resolving; preserve `_decision_problem` and citation guards. Reassignment across existing findings must preserve coverage atomically and not steal a ref from a previously resolved match or leave stale duplicate/missing rows. Otherwise retain unresolved and report the limitation. Reading parent context must never turn parent headings into matched functions automatically.

The model chooses the next investigation tool from intermediate results; no canned sequence pretending to be model tool use. Cover suspected missing/duplicate, owner/delegate ambiguities and the new unit/risk tasks, not only the first unresolved items. Whole-input deterministic coverage continues; show which subset the model actually investigated. The UI action log exposes tool names, arguments, results and short evidence-based reasons, not hidden chain-of-thought.

Team-selected starting bounds: at most 12 model turns, 32 tool calls and 180 seconds per audit investigation, with the existing per-call timeout also enforced. Bound excerpt/search sizes and record omitted/unreviewed scope; do not silently describe a capped run as complete review. These numbers are safety defaults, not organiser requirements or an accuracy target. A limit, invalid output or provider failure returns a clearly partial/degraded result with only validated decisions; no unsupported raw model conclusion is published. Deterministic fallback remains meaningful and must not be labelled successful agent mode. Replace the fixed two-phase path when the measured loop is integrated; do not retain two competing production model workflows.

### Format boundary

DOCX/PDF/XLSX parsers already exist in `ingest/parsers.py`; reuse them. The upload component's default accept list omits XLSX, and the current spreadsheet parser flattens sheets into text without sheet names/cell coordinates. Make the audit flow retain location mapping and use table headers/rows to identify unit/function relationships. Preserve original cell text; do not convert a whole organisational workbook into one fictitious numbered function. Add location metadata only where necessary, alongside existing refs, and update every display/export consumer through the integrator.

Specify the supported DOCX/XLSX versions and document legacy DOC/XLS conversion/unsupported handling. PDF OCR/image-diagram behavior must be measured rather than inferred from an import. An unreadable or unsupported annex is a visible input limitation, never a silent empty-success report. Do not claim arbitrary diagram-layout understanding unless demonstrated. Obtain any missing organiser annex through authorised access; build clearly marked synthetic controls now instead of inventing an organiser source.

## 5. Three parallel participant workstreams

### Batyrkhan — integrated agent and mandatory domain features

**Own:** `apps/api/app/`, root/runtime configuration, schemas/contracts and dependency manifests/lockfiles; coordinate API handoff and final integration. **Do not edit `apps/web/` implementation: Askat owns it in Stage 3.** First land the §4 schemas and engine integration boundary. Then independent builders may own (A) agent loop/tools, (B) unit lineage/conflict logic, (C) format/source-location handling; Main alone owns shared models and HTTP/event integration. One writer per file. Builders do not install dependencies or run repo-wide validation during concurrent edits.

Deliver the M1–M5/F1 backend and provide real Report/trace contracts to Askat for the Russian UI. Consume Alibi's development diagnoses, not expected answers embedded in application code. Independently review unsupported loss, false duplicate and false conflict cases. Acceptance: a successful authorised live-model run with result-dependent actions, source-backed output, bounded stopping and reopened Report; malformed-input/model-failure completion; jointly exercised browser quote navigation in Askat's UI. Existing regression, new control bundle and targeted contract checks run after integration. No claim that fewer abstentions alone means better quality.

### Alibi — independent requirements-level evaluation

**Own:** `eval/kt/`, `seeds/kt/eval/`, `docs/evidence/kt-quality.md`. Keep existing regression, challenge version history and pending-human distinctions. Resolve source-sensitive development disputes transparently; AI consensus is not a human sign-off. Receive the schema revision from Batyrkhan; extend the existing scorer for unit changes/risks without importing private decision helpers. Do not rewrite seven-status function gold into a new schema.

Prepare source-first controls for retained/created/reorganised units, lost duty, true cross-unit duplication, potential conflict, legitimate sharing, split/merge, parent/delegate changes and PDF/XLSX source locations. Include both positive and negative cases; label synthetic inputs as synthetic. Human/source confirmation and hashes precede scored release runs. New unit/risk labels refer to public typed outputs and citations; exact field schema is fixed with the integrator before capture.

Compare **deterministic versus actual agent** on identical input bytes and one integrated core revision. Report TP/FP/FN/abstentions by output type, scope of unreviewed findings, invalid citations and actual tool-use traces separately. Record model/configuration and completed/partial/fallback runs; canned provider responses can test guards but cannot establish agent quality. Do not compare the historical 6/12 development result to a new run as though both used one confirmed gold version. Holdout is scored only after its approval gate; if used for tuning, move it to development. Publish results and remaining gaps, not an invented success threshold.

### Askat — expert workflow, export and deployability

**Own:** `apps/web/` implementation and web container, `scripts/`, README, `docs/architecture.md`, `docs/demo.md`, `docs/business-case.md`, `docs/evidence/kt-launch.md`, `docs/PROGRESS.md`. Dependency manifests/lockfiles remain coordinated exclusively by Batyrkhan. Implement the complete Russian review interface: units, function comparisons, cross-unit risks, analytical conclusion, source locations and honest agent status/actions; add XLSX file selection. Preserve Stage 2 context navigation and exporter/security fixes. After the schema handoff, export all new outputs without dropping roles/context; do not fork backend report construction. Prepare the clean deployment environment and model-access option immediately.

Rehearse the actual main scenario: upload before/after → changed units → loss/duplication → potential conflict → conclusion → exact source → reopen/export. Demonstrate live-agent actions, not merely the checkbox or a recorded keyless report. Fix frontend defects in owned files; send API/backend defects to Batyrkhan with reproduction. Update README/model limits/disclosures from the integrated implementation and use a verified shell command on this host (`sh scripts/demo.sh`, not Windows' WSL `bash.exe`). Root/container fixes outside the web directory go to Batyrkhan. Check source-byte policies across clean checkouts; the known LF/CRLF hash issue is a release blocker, not grounds to weaken SHA checks.

Finish with a pinned-revision disposable launch that does not stop/delete the team's services or expose unauthenticated uploads publicly. Record actual Docker/HTTP/browser/export output; a successful clone or synthetic HTML test is not deployment proof. Explain the reviewer workflow and potential value without invented productivity numbers. Prioritise the live agent and all must-haves over cosmetic export changes.

At integration, reconcile hourly progress against actual commit history. Never fabricate a missing hour, backdate a checkpoint or count this planning handoff as a past run; flag any missing contemporaneous evidence to the team.

## 6. Model access and external-action boundary

Paid coding subscriptions do not supply application inference. Existing `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` and timeout settings remain the configuration boundary. Before sending organiser content or spending credits, obtain explicit approval for provider/model, permitted input set and spend limit; before deployment, approve target/access scope. Do not expose `.env`, keys, whole sensitive reports or raw traces in public evidence.

The runbook mentions organiser OpenAI credits and a Brev token; that is an option to verify, not proof of current permission, deployed access or working inference. Use approved synthetic inputs first. Offer experts either approved non-personal test/demo access to live inference or a tested self-hosted/local model path; BYO-key alone and deterministic fallback alone do not demonstrate the central AI-agent scenario without participant credentials. Recorded traces supplement reproducibility but do not replace a working verification route. If access is unresolved, implement all local guards/tools and mark the live-model acceptance gate blocked; do not fabricate a successful provider run.

## 7. Stage 3 exit and Stage 4 release gate

Stage 3 ends only with the integrated control bundle exercising all M1–M5/F1/D1, a genuine successful agent run, evidence of guard/timeout behavior, all new outputs visible and exported, and a confirmed judge-verification route. Every handoff gives exact owned paths, revision/core hashes, commands, outputs and limitations. No core claim is backed solely by ignored local files.

Stage 4 checks one pinned, integrated revision against the five official rubric rows. Rehearse README on a clean environment without personal credentials; exercise both the agent verification route and keyless degradation; open the actual UI and offline report; validate source hashes, exact citations and saved retrieval. Run final shared checks once after concurrent edits settle, then review evidence and documentation for false claims, exposed secrets, undisclosed dependencies and hardcoded case answers. Do not read frozen holdout answers into the core review. Fix observed release blockers, update progress, commit owned changes after pull/rebase, push normally and freeze by 18:00. No feature stage follows; Demo Day presentation is a separate organiser event.

For execution, each participant starts a main session with this plan plus their own subsection; configured builders/scouts/reviewers are delegated by that session. Start the three human workstreams concurrently. A review agent is read-only and must not share file ownership with a builder. Stage 3 planning itself does not authorise a cloud deployment, paid call or Git push, and this document does not claim any of them occurred.
