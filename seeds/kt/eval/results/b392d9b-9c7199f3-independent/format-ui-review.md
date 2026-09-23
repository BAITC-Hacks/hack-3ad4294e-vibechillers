# Independent format and UI/export review: b392d9b / 9c7199f3

Scope: saved artifacts in `seeds/kt/eval/data/b392d9b-9c7199f3/`, core `b392d9bd18687eb4905f296897399d0a5eb581e9`, schema `4da43907919867ce4e8579360fe5b2ff43f9a37c`. Archive SHA-256: `d11036abe169ace52b1bf9e4c3480b83df31ba2d405ae3d531a6dadd7885681d`.

No provider/network calls, product restart, private alignment-helper import/call, holdout access, dataset extension or scorer change. The reviewer read the original containers independently (DOCX XML, PDF with bundled pypdf, XLSX with bundled openpyxl), viewed the delivered screenshot and parsed HTML as inert text. This is artifact review, not a new live browser or inference run. No labels changed or became human-confirmed.

## Verdicts and owners

| Criterion | Verdict in this review | Concrete evidence / blocker | Owner |
|---|---|---|---|
| M4 | Physical coordinates and saved source links pass within the checked scope; complete semantic source support remains blocked for PDF | DOCX 72/72, PDF 102/102, XLSX 72/72 source texts occur at the exact supplied location. HTML has 445/445 resolving local links and 72/72 Report source texts. PDF main clauses omit wrapped governing text into separate `other` rows. | Batyrkhan: complete parser/context; Askat: multi-format source navigation |
| F1 | **Blocker** | XLSX retains 72 source cells but extracts 0 functions and 0 units; no function/unit/risk comparison. PDF unit/risk output differs materially from DOCX on the same synthetic content. Existing table-layout annex controls are not captured in this ZIP. | Batyrkhan: parser and format handling; Askat: upload/source UI evidence |
| D1 | Saved export and one screenshot target pass; full exit **not established** by this slice | Export JSON equals the completed agent Report as a JSON object. HTML contains all report categories and source rows with no broken internal links or external resources. The screenshot shows one correct DOCX source target. No separate frontend runtime revision or clean launch/judge-access proof, independent browser execution or PDF/XLSX UI navigation evidence is present. | Askat: integrated UI/browser/launch; Batyrkhan: runtime/judge route |

Do not reinterpret D1 evidence limits as a demonstrated UI defect. The exported object and static links work; missing evidence limits the acceptance claim. Root review separately adjudicates agent behavior, guards, semantics and saved DOCX custody.

## Actual format outputs

| Snapshot | Run ID | Clauses | Function-kind clauses | Findings | Unit-change rows | Risks |
|---|---|---:|---:|---:|---|---|
| DOCX deterministic | `2a5b5e1e16b1423193dcff0be2323447` | 72 | 31 | 19 | 3 reorganised, 3 retained, 1 created | 1 duplication, 1 conflict |
| DOCX agent | `9c7199f33a9f4ca3a9a47abfd65b8c6f` | 72 | 31 | 19 | 3 reorganised, 3 retained, 1 created | 1 duplication, 1 conflict |
| PDF deterministic | `a0ecd5b7dcfa4c8d87a19bb0dfe7f69b` | 102 | 31 | 20 | 2 reorganised, 3 retained, 3 unresolved | 1 conflict |
| XLSX deterministic | `7fc1705c69e84eafbbfc44750c6586fc` | 72 | 0 | 0 | 0 | 0 |

All six physical source hashes match the pinned `control/manifest.json` and corresponding Report document hashes. Both PDF and XLSX traces contain contiguous sequences 1–5, one final event last, one matching run ID and a final payload equal to the supplied Report. Their summaries equal the entries in `integration-evidence.json`. Unlike the main DOCX capture, the format folders do not retain separate reopened GET and raw SSE artifacts; their `saved_equal` / `trace_equal` booleans are operator claims beyond the independent Report/final comparison available here. The global integration record attributes the format probes to b392d9b; no separate per-format server-start attestation is provided.

XLSX cells are all `kind=other` in `formats/xlsx-report.json`, with locations on sheet `Приложение`. Warnings explicitly state that no unit/function headers were recognized, rows were kept as source only, and function/risk comparison is unavailable. Empty outputs are a disclosed limitation, not successful negative predictions. No PDF/XLSX product-quality scoring or new label denominator was added.

## PDF blocker is visible in the source

The original before/after PDFs both have two physical pages. Text on each declared Report page was independently located: 102/102 clause fragments, zero location failures. All quoted Report substrings resolve, but retained fragments are not assembled into full numbered duties/governing provisions:

- `after-1 §2.3`, page 1, ends at “Отдел клиентской”. The complete second successor name and allocation of responsibilities continue in `@p20` and `@p21`, both `kind=other`. DOCX keeps the full paragraph. PDF has unresolved `Ucda22c999423` (ЦКО → ОПО) and `U7f70c45224c3` (ОКА), while DOCX has the supported 1:2 reorganisation.
- `after-1 §2.5`, page 1, ends at “не является правопреемником”; `@p26` holds “существовавшего подразделения.” PDF marks СЦС unresolved (`Ud5d62e548344`) where DOCX marks it created.
- `after-1 §10.1`, page 2, ends at “Разделение”; `@p56` contains the full no-scope-split qualifier and ЦРЗ reference. PDF has no cross-unit duplication Risk. It does contain duplicate Finding `F004` (before §3.1 → after §4.1 + §10.1), so duplication is not completely absent from that Report.
- `after-1 §7.4`, page 2, ends at “самостоятельно”; `@p45`/`@p46` hold approval of the conclusion and absence of external approval. The conflict Risk exists, but its §7.4 citation quotes only the primary fragment.

For each of these four examples, concatenating the primary fragment and its explicit `other` children reproduces the DOCX text exactly after whitespace normalization. Content exists in the PDF and is retained somewhere in the Report; source support available to domain output is fragmented. This is a parser/context diagnosis from the artifacts, not a private-helper execution or a claim about all PDF layouts. No table, geometry, image-only PDF, OCR or diagram interpretation was independently established.

Citation denominator distinction: the supplied PDF summary reports 224 exact citations across findings/conclusion/unit changes/risks. Independently, these 224 plus 15 structural-unit definition citations make **239 checked / 0 substring failures**. Each DOCX Report has **243 checked / 0 substring failures** across all sections, including its 15 unit definitions; its analytical-only count is 228 (86 findings + 114 conclusion + 18 unit changes + 10 risks). The DOCX scorer's 243 already includes those unit definitions, so they must not be added again. These technical checks do not alter scorer metrics. XLSX has **0/0 citations, N/A**, because it publishes no analytical output.

## UI/export evidence

`ui/exported-report.json` equals `capture-docx/agent.json` structurally, with the same run ID and every field preserved; raw bytes differ because serialization differs. No claim of byte equality is made.

`ui/report.html` was parsed without executing it. It has 115 unique IDs, 445 internal links, zero missing targets, zero duplicate IDs, no external resources and no script/iframe/object/embed/form elements. All 72 `source-text` entries equal the Report clause-text multiset. It includes 19 Finding articles, 15 structural-unit articles, 7 unit-change articles and 2 Risk articles. Its title names the agent run. The target anchor for `after-1 §10.1` resolves to its full text and block 38, consistent with the Report.

The viewed `ui/source.webp` shows that full highlighted clause in the source panel, after edition, parent §10, and body block 38 explicitly distinguished from a physical page. Tabs display 19 functions, 7 unit changes and 2 risks. Events #51/#52 visibly indicate agent completion and assisted mode. The run ID is not readable in the cropped screenshot itself, so its identity association comes from the package/integration record and consistent content, not independently visible run text. It shows one delivered target state, not every click route.

The integration record names core b392d9b. Its latest `apps/web` ancestry is `93f547987720c81a5bf354264583ab46a55d5db2`, but no separate frontend process revision/hash or launch log binds the screenshot to that checkout. Backend 36 / evaluator 78 / export 6 test counts in `integration-evidence.json` are supplied claims without corresponding raw logs in this archive; this reviewer did not rerun those tests. The two aborted browser GETs are disclosed by the operator; this archive is insufficient to diagnose them as a functional failure.

## Reproduction

Run the root intake command in `eval/kt/BATYRKHAN-CAPTURE.md` against the delivered SHA/core and a fresh extraction/output directory. Do not overwrite prior evidence. Machine checks, exact fragment texts, run identities and artifact hashes are in `format-ui-review.json`.

This read-only check reproduces the central identity, format-count, terminal-payload and HTML-link observations after extraction (standard Python only):

```powershell
@'
import json, collections
from pathlib import Path
from html.parser import HTMLParser
p = Path("seeds/kt/eval/data/b392d9b-9c7199f3")
read = lambda f: json.loads((p/f).read_text(encoding="utf-8"))
assert read("ui/exported-report.json") == read("capture-docx/agent.json")
for fmt in ("pdf", "xlsx"):
    r, t = read(f"formats/{fmt}-report.json"), read(f"formats/{fmt}-trace.json")
    assert [x["seq"] for x in t] == list(range(1, len(t)+1))
    assert sum(x["type"] in ("final", "error") for x in t) == 1
    assert t[-1]["type"] == "final" and t[-1]["data"]["payload"] == r
    assert all(x["run_id"] == r["run_id"] for x in t)
    print(fmt, r["run_id"], collections.Counter(c["kind"] for c in r["clauses"]),
          len(r["findings"]), len(r["unit_changes"]), len(r["risks"]))
class Links(HTMLParser):
    def __init__(self): super().__init__(); self.ids=[]; self.links=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if "id" in a: self.ids.append(a["id"])
        if a.get("href", "").startswith("#"): self.links.append(a["href"][1:])
h=Links(); h.feed((p/"ui/report.html").read_text(encoding="utf-8"))
assert len(h.ids) == len(set(h.ids)) and all(x in h.ids for x in h.links)
print("HTML", len(h.ids), len(h.links), "0 broken links")
'@ | python -B -
```

Physical-coordinate reproduction uses the unchanged `control/{before,after}.{docx,pdf,xlsx}` bytes: read `word/document.xml` body paragraphs in order for DOCX; `pypdf.PdfReader(...).pages[page-1].extract_text()` for PDF; and `openpyxl.load_workbook(..., read_only=True, data_only=False)[sheet][cell_range].value` for XLSX. Check each Report clause text occurs in its declared physical location after whitespace normalization. These are independently readable container coordinates, not helper-derived expectations. The bundled runtime supplies these readers; no dependency installation is necessary.
