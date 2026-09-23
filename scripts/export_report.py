#!/usr/bin/env python3
"""Export a public Function Lineage Auditor Report JSON to offline HTML."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def clause_anchor(doc: str, clause_id: str) -> str:
    key = f"{doc}\x00{clause_id}".encode("utf-8")
    return "clause-" + hashlib.sha256(key).hexdigest()[:16]


def finding_anchor(finding_id: str) -> str:
    return "finding-" + hashlib.sha256(finding_id.encode("utf-8")).hexdigest()[:16]


def clause_link(doc: str, clause_id: str) -> str:
    return f'<a href="#{clause_anchor(doc, clause_id)}">{esc(doc)} §{esc(clause_id)}</a>'


def citation_link(citation: dict[str, Any]) -> str:
    doc = str(citation.get("doc", ""))
    clause_id = str(citation.get("clause_id", ""))
    quote = str(citation.get("quote", ""))
    return (
        f'<a class="citation" href="#{clause_anchor(doc, clause_id)}">'
        f"{esc(doc)} §{esc(clause_id)}: &laquo;{esc(quote)}&raquo;</a>"
    )


def render_report(report: dict[str, Any]) -> str:
    documents = report.get("documents") or []
    clauses = report.get("clauses") or []
    findings = report.get("findings") or []
    conclusion = report.get("conclusion") or []
    warnings = report.get("warnings") or []
    coverage = report.get("coverage") or {}

    document_items = []
    for document in documents:
        source = str(document.get("source", ""))
        if source.startswith(("http://", "https://")):
            source_html = f'<a href="{esc(source)}">{esc(source)}</a>'
        else:
            source_html = esc(source) if source else "(not supplied)"
        document_items.append(
            f"<li><strong>{esc(document.get('doc', ''))}</strong> "
            f"({esc(document.get('edition', ''))}) &mdash; {source_html}</li>"
        )

    warning_html = "".join(f"<li>{esc(warning)}</li>" for warning in warnings)
    warnings_section = (
        f'<section class="warnings"><h2>Warnings</h2><ul>{warning_html}</ul></section>'
        if warnings
        else ""
    )

    conclusion_items = []
    for item in conclusion:
        ids = " ".join(
            f'<a href="#{finding_anchor(str(finding_id))}">{esc(finding_id)}</a>'
            for finding_id in item.get("finding_ids", [])
        )
        citations = " ".join(citation_link(c) for c in item.get("citations", []))
        conclusion_items.append(
            f"<li><p>{esc(item.get('text', ''))}</p>"
            + (f'<p class="meta">Findings: {ids}</p>' if ids else "")
            + (f'<p class="citations">{citations}</p>' if citations else "")
            + "</li>"
        )

    finding_items = []
    for finding in findings:
        refs = []
        for field in ("before", "after"):
            links = " ".join(
                clause_link(str(ref.get("doc", "")), str(ref.get("clause_id", "")))
                for ref in finding.get(field, [])
            )
            refs.append(f"<dt>{esc(field.title())}</dt><dd>{links or 'none'}</dd>")
        citations = " ".join(citation_link(c) for c in finding.get("citations", []))
        review = "yes" if finding.get("review_required") else "no"
        finding_items.append(
            f'<article class="finding" id="{finding_anchor(str(finding.get("id", "")))}">'
            f'<h3><span class="status">{esc(finding.get("status", ""))}</span> '
            f'{esc(finding.get("id", ""))}</h3>'
            f'<p>{esc(finding.get("reason", ""))}</p>'
            f'<p class="meta">Method: {esc(finding.get("method", ""))}; review required: {review}</p>'
            f"<dl>{''.join(refs)}</dl>"
            + (f'<p class="citations">{citations}</p>' if citations else "")
            + "</article>"
        )

    clause_items = []
    for clause in clauses:
        doc = str(clause.get("doc", ""))
        clause_id = str(clause.get("clause_id", ""))
        clause_items.append(
            f'<article class="clause" id="{clause_anchor(doc, clause_id)}">'
            f'<h3>{esc(doc)} §{esc(clause_id)} '
            f'<span class="kind">{esc(clause.get("kind", ""))}</span></h3>'
            f'<p class="label">{esc(clause.get("label", ""))}</p>'
            f'<p>{esc(clause.get("text", ""))}</p></article>'
        )

    coverage_text = ", ".join(
        f"{esc(key.replace('_', ' '))}: {esc(coverage.get(key, ''))}"
        for key in ("before_total", "after_total", "before_accounted", "after_accounted", "unresolved")
        if key in coverage
    )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Function Lineage Auditor report {esc(report.get("run_id", ""))}</title>
<style>body {{ font: 16px/1.5 system-ui,sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 1rem; color: #202124 }}
a {{ color: #075985 }} .meta,.label,.kind {{ color: #5f6368; font-size: .9rem }}
.warnings {{ border: 2px solid #b45309; background: #fff7ed; padding: .75rem 1rem; margin: 1rem 0 }}
.finding,.clause {{ border: 1px solid #d1d5db; padding: .8rem 1rem; margin: .75rem 0; scroll-margin-top: 1rem }}
.finding:target,.clause:target {{ outline: 3px solid #f59e0b }} .status {{ background: #e0f2fe; padding: .15rem .4rem }}
dt {{ font-weight: 700 }} dd {{ margin: 0 0 .35rem }} .citations {{ overflow-wrap: anywhere }}</style></head><body>
<h1>Function Lineage Auditor report</h1>
<p class="meta">Run: {esc(report.get("run_id", ""))}; mode: {esc(report.get("mode", ""))}</p>
<h2>Documents</h2><ul>{''.join(document_items)}</ul>
<h2>Coverage</h2><p>{coverage_text}</p>
{warnings_section}
<section><h2>Conclusion</h2><ol>{''.join(conclusion_items) or '<li>No conclusion supplied.</li>'}</ol></section>
<section><h2>Findings</h2>{''.join(finding_items) or '<p>No findings supplied.</p>'}</section>
<section><h2>Source clauses</h2>{''.join(clause_items) or '<p>No clauses supplied.</p>'}</section>
</body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8-sig"))
    if not isinstance(report, dict):
        raise SystemExit("Report JSON must be an object")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_report(report), encoding="utf-8")
    print(f"HTML report saved to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())