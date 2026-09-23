# Stage 3 synthetic control inputs

This is an author-constructed development bundle for the official control scenario. It is **not organiser data or human-confirmed gold**. All proposed expectations remain `pending_human` in `expectations.preliminary.md`; agreement by an AI reviewer does not confirm product accuracy. No product outputs were used to write the input texts or the preliminary expectations. Holdout sources and answers are not part of this bundle.

The canonical sources are `before.txt` (31 lines) and `after.txt` (41 lines). They specify the complete miniature annex, including explicit unit identity, succession and responsibility scope. DOCX, PDF and XLSX repeat the same text. The XLSX is intentionally a single-column annex, one source paragraph per cell; it contains no formulas or gold answers. Do not upload several equivalent representations together.

## Immediate run

From repository root, with the documented API running on port 8000:

```powershell
curl.exe -N -X POST http://localhost:8000/audits -F "before_files=@seeds/kt/eval/control/before.docx" -F "after_files=@seeds/kt/eval/control/after.docx" -F "use_llm=false" -o control-deterministic.sse
curl.exe -N -X POST http://localhost:8000/audits -F "before_files=@seeds/kt/eval/control/before.docx" -F "after_files=@seeds/kt/eval/control/after.docx" -F "use_llm=true" -o control-agent-request.sse
```

Change both extensions together to `txt`, `pdf` or `xlsx` for a format run. Record commit, manifest SHA-256 values and effective inference configuration before paired runs. `use_llm=true` requests inference; successful HTTP/SSE delivery alone does not prove a real agent ran. Check actual mode, model errors, tool trace and final result. This README makes no claim that either HTTP command has already been executed.

Give independent reviewers only the two canonical text files first. Preserve their source conclusions before revealing `expectations.preliminary.md`. Do not distribute holdout answers with this development handoff.

## Rebuild and verify

`eval/kt/build_control.py` reads canonical TXT; it never obtains or changes gold from product results. Existing binary files are runnable without regeneration. Resolve bundled runtime paths through the workspace dependency loader. Python needs existing `python-docx`, `reportlab` and ingestion dependencies; XLSX generation uses the bundled `@oai/artifact-tool` JavaScript module. No dependencies were installed or modified for this bundle.

```powershell
$runtime = 'C:/Users/torre/.cache/codex-runtimes/codex-primary-runtime/dependencies'
& "$runtime/python/python.exe" eval/kt/build_control.py --formats docx pdf xlsx --node "$runtime/node/bin/node.exe" --artifact-module "$runtime/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs" --verify-inputs
```

On another machine, substitute runtime paths and pass `--font` pointing to a Cyrillic-capable TTF. To reproduce ingestion verification without modifying input bytes or the pinned manifest:

```powershell
uv run --no-sync python eval/kt/build_control.py --verify-inputs
```

Binary container metadata may change on regeneration. Paired product runs must use the same recorded checked-in bytes, not separately regenerated equivalents. `manifest.json` records full file hashes, canonical hashes, synthetic origin, development split and pending status. `format-qa.json` records public ingestion checks and hashes of the parser source files used.

Numbered-reference expectations in format QA are independently resolved from canonical TXT by `eval/kt/score.py:source_clauses`, not by the product parser being checked. The before/after denominators are 29/39 refs, including section and lettered structure markers. QA reports absent, extra and duplicate refs as well as text mismatches and exact unique matches. A missing clause cannot silently disappear from the denominator; ambiguous canonical source boundaries fail verification. Duplicate refs include excess occurrences that the product parser renames using `@2` suffixes.

## Format checks and known limitations

Initial checks on 2026-09-23: all 8 input files have full extracted text equal to canonical text after whitespace normalization; each format extracts 7 before units and 8 after units. TXT, DOCX and XLSX preserve all numbered clause texts. **PDF currently exposes an ingestion defect:** 8 before and 14 after numbered clauses are split at physical line wraps, with continuation lines retained as `kind=other` and excluded from matching. The same complete source text is present in the PDF. This must not be presented as successful semantic PDF parsing. See exact clause IDs and denominators in `format-qa.json`.

Both PDF files were rendered using bundled Poppler and all 4 pages visually inspected: no clipping, overlap or missing Cyrillic glyphs. Both complete XLSX worksheets were rendered with Artifact Tool and visually inspected: no clipped cells. DOCX paragraphs round-trip exactly through the public parser, but **DOCX visual QA is blocked**: the packaged `render_docx.py` reports `FileNotFoundError: LibreOffice soffice.exe was not found on PATH`; the runtime and Program Files search found no renderer. No installation was attempted. DOCX is provided as a runnable engineering test input with this explicit layout-verification limitation, not as a visually certified document.

Reproduce DOCX rendering where LibreOffice is available:

```powershell
python <documents-skill>/render_docx.py seeds/kt/eval/control/before.docx --output_dir <temporary-directory>/before-docx --verbose
python <documents-skill>/render_docx.py seeds/kt/eval/control/after.docx --output_dir <temporary-directory>/after-docx --verbose
```

Authoring formats are independent inputs to test, not evidence of product accuracy. Source expectations, ingestion checks, citations and actual agent behavior must be scored and reported separately.

## Auxiliary table probe

`before-table.xlsx` and `after-table.xlsx` separately test real three-column rows with headers `Пункт`, `Подразделение`, `Функция/основание`, and two worksheets `Структура` and `Функции`. They derive their clauses from the canonical TXT, move the marker to column A, and repeat the governing unit abbreviation in column B. This is an auxiliary **unlabelled format probe**, not an additional gold representation. Its independent `table-probe-manifest.json` marks every entry `auxiliary=true` and records canonical provenance and binary hashes. Original eight pinned inputs and the main manifest remain unchanged.

All four worksheets were rendered and visually inspected. The public parser reads both sheets, yielding 31 before clauses / 7 units and 41 after clauses / 8 units. Its tab-flattened clause text includes the owner column, so extraction counts alone do not verify semantic function matching or table-cell citations. `table-probe-qa.json` preserves representative parsed duty clauses. No audit inference was run by the control-input author.

```powershell
& "$runtime/python/python.exe" eval/kt/build_control.py --auxiliary-tables --node "$runtime/node/bin/node.exe" --artifact-module "$runtime/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs" --verify-tables
uv run --no-sync python eval/kt/build_control.py --verify-tables
curl.exe -N -X POST http://localhost:8000/audits -F "before_files=@seeds/kt/eval/control/before-table.xlsx" -F "after_files=@seeds/kt/eval/control/after-table.xlsx" -F "use_llm=false" -o control-table-deterministic.sse
```
