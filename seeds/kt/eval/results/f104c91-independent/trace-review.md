# Independent review of the saved partial agent trace

This is a separate AI review of saved runtime evidence at core `f104c91006c8d3d6a993881823863030e70aa4af`. It used neither gold labels nor holdout. It did not run product inference and is not human confirmation. The trace and SSE support actual recorded tool activity; they are host-produced records, not cryptographically authenticated proof of remote provider identity or billing.

The attempted agent run `76f223b2a6b44a9b8b68ac0386152e6f` ends **partial / mode=deterministic**. Compared with deterministic run `6b5120b9b2c244c589d36d3cb90c655c`, the only changed top-level fields are `run_id`, `agent`, and one additional partial warning. All 31 findings, seven unit changes, zero risks, conclusion, coverage, clauses, units and documents are identical. There is no observed product-quality uplift and no completed agent finalization.

## Raw action counts and evidence limits

| Observation | Count / denominator |
|---|---:|
| Tool calls paired to successful results by unique call_id | 25 / 25 |
| Mutating proposal calls | 0 / 25 calls |
| Accepted / rejected proposals | 0 / 0 (no proposals attempted) |
| `build_report` calls / successes | 0 / 0 |
| Completed attempted agent captures in this package | 0 / 1 |
| Reported model turns used | 12 / 12 limit |
| Tool budget used | 25 / 32 limit |
| Listed finding rows / unique finding IDs | 37 / 31 |
| Explicitly inspected finding IDs | 22 / 31 |
| `investigated_finding_ids`, reconstructed from public tool semantics | 23 / 31 |
| Listed unit-change rows | 7 / 7 |

The 25 calls consist of 9 `read_clauses`, 7 `search_clauses`, 3 `list_findings`, 3 `inspect_domain`, and 3 `inspect_findings`. There are no `offer_candidates`, `resolve_alignment`, `propose_unit_change`, `propose_risk`, `verify_citations`, or `build_report` calls. Zero tool failures is API execution success, not correctness of the analytic product.

All 60 persisted events have sequential seq IDs. The 25 tool call/result pairs are adjacent and have unique matching call IDs; every result has `ok=true`. Trace and SSE match in seq/type/data for all 60 events. SSE timestamps match within their millisecond rounding. The final event is seq 60; the stop/status events are seq 57 (`turn_limit`), seq 58 (`partial`), and seq 59 (`mode: deterministic`).

The elapsed saved host time from investigation-start seq 6 to stop seq 57 is **50.515491 seconds**, and to final seq 60 is **50.610526 seconds**. The observed stopping reason is the turn cap, with seven tool slots unused; the nominal 180-second wall cap was not exhausted. The report records 12 model turns, but this trace contains no model-turn boundary markers, provider request IDs, raw provider responses, token usage or cost. Timestamp clusters must not be presented as independently verified turn assignments. Actual cost and token counts are unavailable.

## Chronology and result-dependent arguments

The exact arguments, call IDs, adjacent result seq IDs, elapsed times and newly marked inspection IDs are in `trace-review.json`, one record for each of the 25 calls.

1. **Seq 7-16: triage and paging.** `list_findings` returns F002-F005, F009 and F016 at seq 8. All six become the arguments to `inspect_findings` at seq 15 (`call_57ac3cfc6a2748a199a4843e`). `inspect_domain(unit_changes)` returns `next_offset=6` at seq 10; seq 13 (`call_5045988f64634285b2866080`) requests that offset and obtains the seventh unit row. `inspect_domain(risks)` returns an empty list at seq 12.
2. **Seq 17-24: inspect archival loss and transferred control.** Seq 19/20 reads before 2.2 and 7.1; seq 21/22 reads after 7.4 and 2.6. The archive-retention wording received at seq 20 reappears in the after-edition query at seq 23 (`call_df3b6fa2560e46e4b89892ee`). The search returns a different archival duty and lower-similarity candidates. No resolution follows.
3. **Seq 25-34: broader finding inventory and ownership context.** Seq 25 lists unchanged/changed/moved/added findings. Seq 27 follows offset 16 but drops the status filter. That repeats six IDs, F017-F022; nevertheless all three listing results collectively include all 31 IDs. Seq 29 inspects eight other findings. Seq 31 searches the archive owner, and seq 33 reads the before/after headings.
4. **Seq 35-46: examine supplier-control ownership.** Reads and searches reach the old financial-control heading, the new supply-center heading, created-service text, the supplier-selection duty, and the preserved financial-control unit. Seq 43/44 (`call_93e2c4a1fea14664aef56c99`) discovers the after financial-control heading at 8; seq 47 then reads that returned heading.
5. **Seq 47-56: finance-cooperation clauses and more inspection.** Seq 47/48 reads after 8 and 8.1. Seq 49/50 searches the same owner after and repeats 8.1 as its top result. Seq 51/52 (`call_19194ab180a94d0bbc046db6`) returns before 7.2, which is read at seq 53 (`call_5ccad41e15e9482a99cf422e`). Seq 55 inspects eight more IDs. There is still no proposal or finalizer.
6. **Seq 57-60: turn limit and host output.** The host rebuilds and emits the deterministic analytic state with partial metadata. This is distinct from a model-issued `build_report`; the latter never occurs in the trace.

These are observable argument/result links and a chronology of saved events. They show selected source evidence being followed in later calls. They do not expose the model's private reasoning or independently authenticate which provider generated the calls.

## What 23/31 means

At this core, `AuditContext.inspect_findings` marks requested IDs after exposing bounded finding details (`apps/api/app/agent/audit_tools.py:261`, marking at line 291). `read_clauses` marks any finding whose before/after ref matches a requested source (`:414`, marking at line 433). Listing, searching and `inspect_domain` do not themselves mark finding IDs.

The three explicit inspection calls contain 22 unique IDs. Reading after 2.5 at seq 37 additionally marks F029, yielding exactly the reported 23. The eight remaining IDs are F023, F024, F025, F026, F027, F028, F030 and F031. These counts denote exposure to evidence, not 23 verified resolutions, 23 correct judgments, or 23 complete reviews. Some inspected finding citations are bounded. In unit inspection, five citations are omitted across the three reorganisation rows on the first page. Seven listed unit rows therefore do not establish complete source review.

The verified core code contains a host finalization path (`apps/api/app/agent/audit_llm.py:77`) that rebuilds current validated state even after limit failure. `AuditContext.build` chooses deterministic mode in the absence of accepted model decisions (`apps/api/app/agent/audit_tools.py:823`). Both mechanisms agree with the recorded zero-decision fallback; the host's generic 'verified decisions retained' message is not evidence that this model accepted any decisions.

## Evidence reached without changing the product

- **Potential self-review conflict:** seq 16, 20 and 22 expose the old independent procurement check, explicit transfer to the supply center, and the supply center's self-approval text. Seq 30 and 40 expose its supplier-selection duty as well. Thus the model received the relevant execution-and-self-review material. No `propose_risk` or `resolve_alignment` call is made. Risks remain empty and F016 remains unresolved. This is an observed unaddressed source-backed concern, not proof of a legal violation.
- **Possible duplicate registration duty:** after 4.1 is present in the F010 inspection; the counterpart after 10.1 never appears in any intermediate tool result, including nested source context. F030 appears only as a brief added-finding list row. The full saved parsed after 10.1 assigns the same registration duty to the digital-service unit and explicitly leaves its allocation with the registration center undivided. The trace therefore does not establish examination of both sides of this concern. Source-first raw DOCX verification and label adjudication remain separate from this trace review.
- **Archival-retention duty:** the old before 2.2 duty is read and searched against the new edition. The first search result is a different archive-register duty. No exhaustive after-function enumeration or model proposal occurs. Existing F009 remains missing with cautious host wording; a search hit list alone is not proof of organizational loss.
- **Allowed cooperation:** after 8.1 is fully read and states financial approval with explicit exclusion of technical approval. The final inspection includes F018, whose source is the technical counterpart. Zero risk output here cannot be credited as an affirmative model discrimination: the model made zero risk proposals of any kind and retained the baseline throughout.

## Review findings and follow-up evidence

The central failure is failure to finalize or make any guarded analytic proposal within the allotted turns, despite 25 successful inspection/search calls. Additional repeat work is visible: filter-changing pagination repeats six findings; the old financial-control heading is searched after it was read; the after finance clause is searched immediately after it was read. These observations support investigation of turn use, without labeling all exploratory search unnecessary.

A future live completion package should retain this baseline and record a separate run ID and configuration. It should make successful `build_report`, any proposed/accepted/rejected changes, and their result-dependent evidence inspectable. Turn-boundary telemetry and nonsecret provider request/usage metadata would permit a firmer audit of iteration budget and provider provenance. This review supplies no new gold, no holdout, no F1, and no Stage 3 acceptance claim.
