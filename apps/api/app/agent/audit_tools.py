"""Typed, run-scoped audit investigation tools.

The host parses and aligns once. The model's registry contains no operation
that can parse, realign, reset findings, access a path or make network calls.
Candidate search is evidence discovery, not a match: offering and resolution
are separate guarded steps, and transfers preserve coverage atomically.
"""

from __future__ import annotations

import copy
import re
import threading
import time
from functools import partial
from collections import Counter
from typing import Any, Literal

import anyio.to_thread
from pydantic import BaseModel, Field

from ..audit import (
    FINDING_STATUSES, AgentExecution, Citation, Clause, ClauseRef, ConclusionItem,
    Document, Finding, Report, Risk, Unit, UnitChange, UnitRef,
)
from ..audit import align_functions as _domain_align
from ..audit import build_report as _domain_build_report
from ..audit import parse_documents as _domain_parse
from ..audit import resolve_alignment as _domain_resolve
from ..audit import verify_citations as _domain_verify
from ..audit.citations import cite_context, clause_index
from ..audit.lineage import validate_risk, validate_unit_change
from ..audit.text import normalize, similarity, stems
from .tools import Tool, ToolRegistry

__all__ = ["AUDIT_TOOL_NAMES", "AuditContext", "create_audit_registry"]

AUDIT_TOOL_NAMES = (
    "list_findings", "inspect_findings", "read_clauses", "search_clauses",
    "inspect_units", "search_units", "inspect_domain", "offer_candidates",
    "resolve_alignment", "propose_unit_change", "propose_risk",
    "verify_citations", "build_report",
)
STATUSES: tuple[str, ...] = FINDING_STATUSES
_CLAUSE_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3})+)(?!\.?\d)(?!\w)")
_CONTEXT_TERMS = re.compile(
    r"не\s+(?:вправе|может|допускается)|запрещ|исключител|обязан|должен|"
    r"ответствен|возлага|поруча|делегир|уполномоч|подчин|осуществля|"
    r"в\s+пределах\s+полномоч|за\s+исключением", re.I,
)
_RESTRICTION = re.compile(r"не\s+(?:вправе|может|допускается)|запрещ|исключител|за\s+исключением", re.I)
_PAGE_CHARS = 1400
_EXCERPT_CHARS = 260
_MAX_PARENTS = 6
_MAX_UNITS = 6


def _key(ref: ClauseRef | Citation) -> tuple[str, str]:
    return ref.doc, ref.clause_id


def _unit_key(ref: UnitRef | Unit) -> tuple[str, str]:
    return ref.doc, ref.unit_id


def _base(clause_id: str) -> str:
    return clause_id.split("/", 1)[0].split("@", 1)[0]


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _excerpt(clause: Clause, offset: int = 0, limit: int = _EXCERPT_CHARS) -> dict[str, Any]:
    start = min(offset, len(clause.text))
    end = min(len(clause.text), start + limit)
    return {
        "citation": {"doc": clause.doc, "clause_id": clause.clause_id, "quote": clause.text[start:end]},
        "offset": start, "total_chars": len(clause.text),
        "omitted_before": start, "omitted_after": len(clause.text) - end,
        "next_offset": end if end < len(clause.text) else None,
    }


def _context_excerpts(clause: Clause) -> list[dict[str, Any]]:
    starts = [0]
    match = _RESTRICTION.search(clause.text, _EXCERPT_CHARS) or _CONTEXT_TERMS.search(clause.text, _EXCERPT_CHARS)
    if match:
        starts.append(max(0, match.start() - 35))
    result = []
    for start in starts:
        if not any(row["offset"] <= start < row["offset"] + len(row["citation"]["quote"]) for row in result):
            result.append(_excerpt(clause, start))
    return result


def _page(rows: list[Any], offset: int, limit: int, label: str) -> dict[str, Any]:
    return {label: rows[offset:offset + limit], "total": len(rows), "offset": offset,
            "next_offset": offset + limit if offset + limit < len(rows) else None,
            "omitted_before": min(offset, len(rows)), "omitted_after": max(0, len(rows) - offset - limit)}


class AuditContext:
    """One report's mutable, guarded decisions and immutable source documents."""

    def __init__(
        self, run_id: str, documents: list[Document],
        pages_by_doc: dict[str, list[dict[str, Any]]] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        aliases = [d.doc for d in documents]
        if len(set(aliases)) != len(aliases):
            raise ValueError(f"document aliases must be unique within a run, got {aliases}")
        self.run_id = run_id
        self.documents = list(documents)
        self._pages = dict(pages_by_doc or {})
        unknown = sorted(set(self._pages) - set(aliases))
        if unknown:
            raise ValueError(f"pages supplied for documents outside this run: {unknown}")
        self.base_warnings = list(warnings or [])
        self.parse_warnings: list[str] = []
        self.warnings: list[str] = []
        self.clauses_by_doc: dict[str, list[Clause]] = {}
        self.units_by_doc: dict[str, list[Unit]] = {}
        self.findings: dict[str, Finding] = {}
        self.offered: dict[str, Finding] = {}
        self.unit_changes: list[UnitChange] = []
        self.risks: list[Risk] = []
        self.agent: AgentExecution | None = None
        self.last_report: Report | None = None
        self._searched_refs: set[tuple[str, str]] = set()
        self._read_ranges: dict[tuple[str, str], list[tuple[int, int]]] = {}
        self._predecessor_searches: set[tuple[str, str]] = set()
        self.investigated_finding_ids: set[str] = set()
        self._inspected_sources = 0
        self._lock = threading.Lock()
        self.deadline: float | None = None

    async def invoke(self, operation: str, **kwargs: Any) -> dict[str, Any]:
        """Run a tool on isolated mutable state; cancellation cannot commit late."""
        state = (
            "findings", "offered", "unit_changes", "risks", "warnings",
            "_searched_refs", "_read_ranges", "_predecessor_searches",
            "investigated_finding_ids", "_inspected_sources", "last_report",
        )
        working = copy.copy(self)
        working._lock = threading.Lock()
        for field in state:
            value = getattr(self, field)
            if field == "_read_ranges":
                value = {key: ranges.copy() for key, ranges in value.items()}
            elif isinstance(value, (dict, list, set)):
                value = value.copy()
            setattr(working, field, value)
        result = await anyio.to_thread.run_sync(
            partial(getattr(working, operation), **kwargs), abandon_on_cancel=True,
        )
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise TimeoutError("Audit deadline expired; tool state was not committed.")
        for field in state:
            setattr(self, field, getattr(working, field))
        return result

    @classmethod
    def from_report(
        cls, report: Report, pages_by_doc: dict[str, list[dict[str, Any]]] | None = None,
    ) -> AuditContext:
        ctx = cls(report.run_id, report.documents, pages_by_doc, report.warnings)
        for doc in ctx.documents:
            ctx.clauses_by_doc[doc.doc] = [c for c in report.clauses if c.doc == doc.doc]
            ctx.units_by_doc[doc.doc] = [u for u in report.units if u.doc == doc.doc]
        ctx._set_findings(report.findings)
        ctx.unit_changes = [change.model_copy(deep=True) for change in report.unit_changes]
        ctx.risks = [risk.model_copy(deep=True) for risk in report.risks]
        ctx.agent = report.agent
        return ctx

    @property
    def clauses(self) -> list[Clause]:
        return [c for d in self.documents for c in self.clauses_by_doc.get(d.doc, [])]

    @property
    def units(self) -> list[Unit]:
        return [u for d in self.documents for u in self.units_by_doc.get(d.doc, [])]

    def _document(self, alias: str) -> Document:
        for doc in self.documents:
            if doc.doc == alias:
                return doc
        raise ValueError(f"document {alias!r} is not part of this run")

    def _clause(self, ref: ClauseRef) -> Clause:
        for clause in self.clauses_by_doc.get(ref.doc, []):
            if clause.clause_id == ref.clause_id:
                return clause
        raise ValueError(f"clause {ref.doc}:{ref.clause_id} is not part of this run")

    def _unit(self, ref: UnitRef) -> Unit:
        for unit in self.units_by_doc.get(ref.doc, []):
            if unit.unit_id == ref.unit_id:
                return unit
        raise ValueError(f"unit {ref.doc}:{ref.unit_id} is not part of this run")

    def _set_findings(self, findings: list[Finding]) -> None:
        ids = [f.id for f in findings]
        if len(set(ids)) != len(ids):
            raise ValueError("finding IDs must be unique within a run")
        self.findings = {f.id: f for f in findings}
        self.offered = {f.id: f.model_copy(deep=True) for f in findings}
        self.last_report = None

    # Host-only operations; deliberately absent from create_audit_registry.
    def parse_regulations(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        docs = [Document.model_validate(d) for d in documents]
        if not docs:
            raise ValueError("documents must name at least one document of this run")
        for doc in docs:
            if self._document(doc.doc) != doc or doc.doc not in self._pages:
                raise ValueError(f"document {doc.doc!r} does not match a held source of this run")
        with self._lock:
            result = _domain_parse(docs, {d.doc: self._pages[d.doc] for d in docs})
            for doc in docs:
                self.clauses_by_doc[doc.doc] = [c for c in result.clauses if c.doc == doc.doc]
                self.units_by_doc[doc.doc] = [u for u in result.units if u.doc == doc.doc]
            self.parse_warnings = _dedupe([*self.parse_warnings, *result.warnings])
            self._set_findings([])
        return result.model_dump(mode="json")

    def align_functions(self, before_docs: list[str], after_docs: list[str]) -> dict[str, Any]:
        if not before_docs or not after_docs or set(before_docs) & set(after_docs):
            raise ValueError("align_functions needs distinct before and after document sets")
        for side, aliases in (("before", before_docs), ("after", after_docs)):
            for alias in aliases:
                if self._document(alias).edition != side or alias not in self.clauses_by_doc:
                    raise ValueError(f"document {alias!r} is not a parsed {side} source")
        chosen = set(before_docs) | set(after_docs)
        with self._lock:
            findings = _domain_align(
                [c for c in self.clauses if c.doc in chosen],
                [u for u in self.units if u.doc in chosen], before_docs, after_docs,
            )
            self._set_findings(findings)
        return {"findings": [f.model_dump(mode="json") for f in findings]}

    # Read/search tools. Every page advertises the size of its unshown scope.
    def list_findings(self, statuses: list[str] | None = None, offset: int = 0, limit: int = 8) -> dict[str, Any]:
        if statuses and any(s not in STATUSES for s in statuses):
            raise ValueError("unknown finding status in filter")
        selected = [f for f in self.findings.values() if not statuses or f.status in statuses]
        rows = [{
            "id": f.id, "status": f.status, "method": f.method,
            "before_count": len(f.before), "after_count": len(f.after),
            "review_required": f.review_required,
        } for f in selected]
        page = _page(rows, offset, limit, "findings")
        page["total_all_statuses"] = len(self.findings)
        counts = Counter(f.status for f in self.findings.values())
        page["status_counts"] = {status: counts[status] for status in STATUSES}
        return page

    def inspect_findings(self, finding_ids: list[str], ref_offset: int = 0, ref_limit: int = 12) -> dict[str, Any]:
        if len(set(finding_ids)) != len(finding_ids):
            raise ValueError("finding IDs must be distinct")
        selected = []
        for fid in finding_ids:
            finding = self.findings.get(fid)
            if finding is None:
                raise ValueError(f"finding {fid!r} is not part of this run")
            selected.append(finding)
        rows = []
        for finding in selected:
            before, after = finding.before[ref_offset:ref_offset + ref_limit], finding.after[ref_offset:ref_offset + ref_limit]
            rows.append({
                "id": finding.id, "status": finding.status, "method": finding.method,
                "review_required": finding.review_required,
                "reason": finding.reason[:500], "reason_omitted_chars": max(0, len(finding.reason) - 500),
                "before": [r.model_dump(mode="json") for r in before],
                "after": [r.model_dump(mode="json") for r in after],
                "total_before_refs": len(finding.before), "total_after_refs": len(finding.after),
                "ref_offset": ref_offset,
                "next_before_offset": ref_offset + ref_limit if ref_offset + ref_limit < len(finding.before) else None,
                "next_after_offset": ref_offset + ref_limit if ref_offset + ref_limit < len(finding.after) else None,
                "omitted_before_refs": max(0, len(finding.before) - ref_offset - ref_limit),
                "omitted_after_refs": max(0, len(finding.after) - ref_offset - ref_limit),
                "citations": [{
                    "doc": c.doc, "clause_id": c.clause_id, "quote": c.quote[:_EXCERPT_CHARS],
                    "omitted_quote_chars": max(0, len(c.quote) - _EXCERPT_CHARS),
                } for c in finding.citations[:4]],
                "omitted_citations": max(0, len(finding.citations) - 4),
            })
        self.investigated_finding_ids.update(finding_ids)
        self._inspected_sources += 1
        return {"findings": rows, "total_requested": len(finding_ids)}

    def _context(self, source: Clause) -> dict[str, Any]:
        by_clause = {c.clause_id: c for c in self.clauses_by_doc[source.doc]}
        by_unit = {u.unit_id: u for u in self.units_by_doc[source.doc]}
        chain: list[Clause] = []
        seen = {source.clause_id}
        parent_id = source.parent_id
        stop: dict[str, str] | None = None
        while parent_id and len(chain) < _MAX_PARENTS:
            if parent_id in seen or parent_id not in by_clause:
                stop = {"reason": "cycle" if parent_id in seen else "missing_parent", "parent_id": parent_id}
                break
            parent = by_clause[parent_id]
            chain.append(parent)
            seen.add(parent_id)
            parent_id = parent.parent_id
        if parent_id and stop is None:
            stop = {"reason": "parent_limit", "parent_id": parent_id}
        roles_by_source: dict[str, list[Unit]] = {}
        for unit in by_unit.values():
            if unit.kind == "role":
                for cite in unit.citations:
                    definition = by_clause.get(cite.clause_id)
                    if cite.doc == source.doc and definition and cite.quote and cite.quote in definition.text:
                        found = roles_by_source.setdefault(cite.clause_id, [])
                        if not any(existing.unit_id == unit.unit_id for existing in found):
                            found.append(unit)
        governing: list[Unit] = []
        role_source = "no cited governing role"
        sibling: Clause | None = None
        for ancestor in (source, *chain):
            governing = roles_by_source.get(ancestor.clause_id, [])
            if governing:
                role_source = "cited source ancestor"
                break
        if not governing:
            # Stage-2 scope convention: a numbered heading can be a function,
            # and an unnumbered colon role title scopes later siblings until
            # the next cited role/heading boundary. Its parser parent may
            # differ from that of the numbered children.
            next_parent: dict[str, str | None] = {}
            following: Clause | None = None
            for row in sorted(by_clause.values(), key=lambda c: c.ordinal, reverse=True):
                next_parent[row.clause_id] = following.parent_id if following else None
                if row.label:
                    following = row
            boundaries: dict[str | None, list[Clause]] = {}
            for row in by_clause.values():
                if row.parent_id is None:
                    continue
                unnumbered = not row.label and row.clause_id.startswith("@p") and row.text.rstrip().endswith(":")
                if unnumbered or row.clause_id in roles_by_source:
                    scope = next_parent[row.clause_id] if unnumbered else row.parent_id
                    boundaries.setdefault(scope, []).append(row)
            for branch in (source, *chain):
                if branch.parent_id is None:
                    continue
                prior = [row for row in boundaries.get(branch.parent_id, []) if row.ordinal < branch.ordinal]
                if not prior:
                    continue
                latest = max(prior, key=lambda c: c.ordinal)
                if not latest.label and latest.clause_id.startswith("@p") and latest.text.rstrip().endswith(":"):
                    governing = [u for u in roles_by_source.get(latest.clause_id, [])
                                 if u.unit_id in source.unit_ids]
                    if governing:
                        role_source = "cited preceding sibling role heading"
                        sibling = latest
                break
        linked: list[Unit] = []
        linked_ids: set[str] = set()
        stops: list[dict[str, str]] = []
        for uid in _dedupe([u.unit_id for u in governing] + source.unit_ids):
            unit = by_unit.get(uid)
            visited: set[str] = set()
            while unit is not None:
                if unit.unit_id in visited:
                    stops.append({"reason": "cycle", "unit_id": unit.unit_id})
                    break
                visited.add(unit.unit_id)
                if unit.unit_id not in linked_ids:
                    if len(linked) >= _MAX_UNITS:
                        stops.append({"reason": "unit_limit", "unit_id": unit.unit_id})
                        break
                    linked.append(unit)
                    linked_ids.add(unit.unit_id)
                unit = by_unit.get(unit.parent_unit_id) if unit.parent_unit_id else None
        return {
            "parent_chain_nearest_first": [{
                "doc": c.doc, "clause_id": c.clause_id, "kind": c.kind,
                "source_excerpts": _context_excerpts(c),
            } for c in chain], "parent_chain_stop": stop,
            "sibling_role_scope": ({"doc": sibling.doc, "clause_id": sibling.clause_id,
                                    "source_excerpts": _context_excerpts(sibling)} if sibling else None),
            "governing_role_unit_ids": [u.unit_id for u in governing],
            "governing_role_note": role_source if len(governing) <= 1 else role_source + "; multiple roles, ownership ambiguous",
            "associated_unit_ids_not_ownership_proof": source.unit_ids[:12],
            "omitted_associated_units": max(0, len(source.unit_ids) - 12),
            "linked_unit_definitions": [self._unit_view(u) for u in linked],
            "omitted_linked_units": max(0, len(source.unit_ids) - len(linked)),
            "unit_chain_stops": stops[:_MAX_UNITS],
            "omitted_unit_chain_stops": max(0, len(stops) - _MAX_UNITS),
        }

    def _unit_view(self, unit: Unit) -> dict[str, Any]:
        by_clause = {c.clause_id: c for c in self.clauses_by_doc[unit.doc]}
        cites = []
        for citation in unit.citations[:3]:
            source = by_clause.get(citation.clause_id)
            if source and citation.doc == unit.doc and citation.quote and citation.quote in source.text:
                # A bounded substring is still verbatim; full source is available via read_clauses.
                cites.append({"citation": {"doc": citation.doc, "clause_id": citation.clause_id,
                                             "quote": citation.quote[:_EXCERPT_CHARS]},
                              "omitted_quote_chars": max(0, len(citation.quote) - _EXCERPT_CHARS)})
        return {
            "doc": unit.doc, "unit_id": unit.unit_id, "name": unit.name[:180],
            "omitted_name_chars": max(0, len(unit.name) - 180), "kind": unit.kind,
            "parent_unit_id": unit.parent_unit_id,
            "source_citations": cites, "omitted_citations": max(0, len(unit.citations) - 3),
        }

    def read_clauses(self, refs: list[ClauseRef | dict[str, Any]], offset: int = 0, limit: int = _PAGE_CHARS) -> dict[str, Any]:
        typed = [ClauseRef.model_validate(raw) for raw in refs]
        sources = [self._clause(ref) for ref in typed]
        rows = []
        for ref, clause in zip(typed, sources, strict=True):
            rows.append({
                "doc": clause.doc, "clause_id": clause.clause_id,
                "kind": clause.kind, "label": clause.label, "parent_id": clause.parent_id,
                "location": clause.location.model_dump(mode="json") if clause.location else None,
                "source": _excerpt(clause, offset, limit),
                "context_only": self._context(clause),
            })
        for ref, clause in zip(typed, sources, strict=True):
            self._searched_refs.add(_key(ref))
            self._read_ranges.setdefault(_key(ref), []).append(
                (min(offset, len(clause.text)), min(offset + limit, len(clause.text)))
            )
            for finding in self.findings.values():
                if ref in finding.before or ref in finding.after:
                    self.investigated_finding_ids.add(finding.id)
        self._inspected_sources += len(rows)
        return {"clauses": rows, "total_requested": len(refs)}

    def search_clauses(
        self, query: str, edition: Literal["before", "after"] | None = None,
        doc: str | None = None, kind: Literal["function", "structure", "heading", "other"] | None = "function",
        offset: int = 0, limit: int = 6,
    ) -> dict[str, Any]:
        if doc is not None and edition is not None and self._document(doc).edition != edition:
            raise ValueError("document alias does not belong to requested edition")
        if doc is not None:
            self._document(doc)
        query_norm, query_stems = normalize(query), stems(query)
        matches = []
        scanned = 0
        for clause in self.clauses:
            if (edition and self._document(clause.doc).edition != edition) or (doc and clause.doc != doc) or (kind and clause.kind != kind):
                continue
            scanned += 1
            target_norm, target_stems = normalize(clause.text), stems(clause.text)
            score = similarity(query_norm, query_stems, target_norm, target_stems)
            if query_norm and query_norm in target_norm:
                score = max(score, 1.0)
            if not score:
                continue
            first = clause.text.lower().find(query.lower())
            start = max(0, first - 60) if first >= 0 else 0
            matches.append((score, clause.ordinal, {
                "ref": {"doc": clause.doc, "clause_id": clause.clause_id},
                "kind": clause.kind, "score": round(score, 3),
                "source": _excerpt(clause, start),
                "location": clause.location.model_dump(mode="json") if clause.location else None,
            }))
        matches.sort(key=lambda item: (-item[0], item[1]))
        rows = [entry for _, _, entry in matches]
        shown = rows[offset:offset + limit]
        self._searched_refs.update((r["ref"]["doc"], r["ref"]["clause_id"]) for r in shown)
        page = _page(rows, offset, limit, "matches")
        page["scanned_scope"] = scanned
        return page

    def inspect_units(self, units: list[UnitRef | dict[str, Any]]) -> dict[str, Any]:
        refs = [UnitRef.model_validate(unit) for unit in units]
        if len({_unit_key(u) for u in refs}) != len(refs):
            raise ValueError("unit refs must be distinct")
        rows = [self._unit_view(self._unit(ref)) for ref in refs]
        self._inspected_sources += len(rows)
        return {"units": rows, "total_requested": len(units)}

    def inspect_domain(self, kind: Literal["unit_changes", "risks"], offset: int = 0, limit: int = 6) -> dict[str, Any]:
        """Page existing domain outputs before adding a potentially duplicate claim."""
        outputs = self.unit_changes if kind == "unit_changes" else self.risks
        rows = []
        for output in outputs[offset:offset + limit]:
            row: dict[str, Any] = {
                "id": output.id, "reason": output.reason[:400],
                "omitted_reason_chars": max(0, len(output.reason) - 400),
                "method": output.method, "review_required": output.review_required,
                "citations": [{
                    "doc": citation.doc, "clause_id": citation.clause_id,
                    "quote": citation.quote[:_EXCERPT_CHARS],
                    "omitted_quote_chars": max(0, len(citation.quote) - _EXCERPT_CHARS),
                } for citation in output.citations[:2]],
                "omitted_citations": max(0, len(output.citations) - 2),
            }
            if isinstance(output, UnitChange):
                row.update(status=output.status,
                           before=[r.model_dump(mode="json") for r in output.before[:8]],
                           after=[r.model_dump(mode="json") for r in output.after[:8]],
                           omitted_before_refs=max(0, len(output.before) - 8),
                           omitted_after_refs=max(0, len(output.after) - 8))
            else:
                row.update(kind=output.kind,
                           units=[u.model_dump(mode="json") for u in output.units[:8]],
                           refs=[r.model_dump(mode="json") for r in output.refs[:8]],
                           omitted_unit_refs=max(0, len(output.units) - 8),
                           omitted_clause_refs=max(0, len(output.refs) - 8))
            rows.append(row)
        return {kind: rows, "total": len(outputs), "offset": offset,
                "next_offset": offset + limit if offset + limit < len(outputs) else None,
                "omitted_before": min(offset, len(outputs)),
                "omitted_after": max(0, len(outputs) - offset - limit)}

    def search_units(
        self, query: str | None = None,
        edition: Literal["before", "after"] | None = None,
        predecessor_for: UnitRef | None = None,
        offset: int = 0, limit: int = 8,
    ) -> dict[str, Any]:
        if predecessor_for is not None:
            predecessor_for = UnitRef.model_validate(predecessor_for)
        if predecessor_for is not None:
            if self._document(predecessor_for.doc).edition != "after":
                raise ValueError("predecessor_for must be an after-edition unit")
            target = self._unit(predecessor_for)
            if target.kind != "unit":
                raise ValueError("predecessor search requires a structural after unit")
            if edition not in (None, "before"):
                raise ValueError("predecessor search must examine the before edition")
            edition = "before"
            query = target.name
        if not query or not query.strip():
            raise ValueError("provide a query or predecessor_for")
        query_norm, query_stems = normalize(query), stems(query)
        selected = [u for u in self.units
                    if (edition is None or self._document(u.doc).edition == edition)
                    and (predecessor_for is None or u.kind == "unit")]
        scores = [(similarity(query_norm, query_stems, normalize(u.name), stems(u.name)), u)
                  for u in selected]
        scores.sort(key=lambda pair: (-pair[0], pair[1].doc, pair[1].unit_id))
        rows = [{**self._unit_view(u), "score": round(score, 3)}
                for score, u in scores[offset:offset + limit]]
        # Unlike a name-only lookup, this search scans the *entire* before set
        # (including zero-score alternatives) and reports exactly what is omitted.
        if predecessor_for is not None:
            self._predecessor_searches.add(_unit_key(predecessor_for))
        return {
            "units": rows, "total": len(scores), "offset": offset,
            "next_offset": offset + limit if offset + limit < len(scores) else None,
            "omitted_before": min(offset, len(scores)),
            "omitted_after": max(0, len(scores) - offset - limit),
            "scanned_scope": len(selected),
        }

    # Mutation tools. Reject without changing state; never silently overwrite a match.
    def offer_candidates(self, finding_id: str, before: list[ClauseRef | dict[str, Any]], after: list[ClauseRef | dict[str, Any]]) -> dict[str, Any]:
        before = [ClauseRef.model_validate(ref) for ref in before]
        after = [ClauseRef.model_validate(ref) for ref in after]
        with self._lock:
            current = self.findings.get(finding_id)
            if current is None:
                raise ValueError(f"finding {finding_id!r} is not part of this run")
            if current.status not in ("unresolved", "missing", "added") or current.method == "llm":
                raise ValueError("only unresolved or unpaired added/missing findings can receive new candidates")
            added = before + after
            if not added:
                raise ValueError("offer at least one candidate")
            if len({_key(r) for r in added}) != len(added):
                raise ValueError("offered candidates must be distinct")
            existing = {_key(r) for r in current.before + current.after}
            for side, refs in (("before", before), ("after", after)):
                for ref in refs:
                    clause = self._clause(ref)
                    if clause.kind != "function" or self._document(ref.doc).edition != side:
                        raise ValueError(f"{ref.doc}:{ref.clause_id} is not a {side} function")
                    if _key(ref) not in self._searched_refs and _key(ref) not in existing:
                        raise ValueError(f"{ref.doc}:{ref.clause_id} was not inspected or returned by run-local search")
                    for fid, other in self.findings.items():
                        if fid != finding_id and (ref in other.before or ref in other.after):
                            if other.status not in ("unresolved", "added", "missing") or other.method == "llm":
                                raise ValueError(f"{ref.doc}:{ref.clause_id} belongs to resolved finding {fid}")
            new_before = list({_key(r): r for r in [*current.before, *before]}.values())
            new_after = list({_key(r): r for r in [*current.after, *after]}.values())
            if len(new_before) == len(current.before) and len(new_after) == len(current.after):
                return {"accepted": True, "changed": False, "reason": "every candidate was already offered", "finding": current.model_dump(mode="json")}
            proposed = current.model_copy(update={
                "status": "unresolved", "before": new_before, "after": new_after,
                "citations": cite_context(new_before + new_after, clause_index(self.clauses),
                                          {(u.doc, u.unit_id): u for u in self.units}),
                "reason": current.reason + " [Дополнительные кандидаты из поиска; соответствие не установлено.]",
                "review_required": True,
            })
            self.findings[finding_id] = proposed
            self.offered[finding_id] = proposed.model_copy(deep=True)
            self.last_report = None
            return {"accepted": True, "finding": proposed.model_dump(mode="json")}

    def _fully_read(self, ref: ClauseRef) -> bool:
        source = self._clause(ref)
        end = 0
        for start, stop in sorted(self._read_ranges.get(_key(ref), [])):
            if start > end:
                break
            end = max(end, stop)
        return end >= len(source.text)

    def _decision_problem(self, offered: Finding, result: Finding) -> str | None:
        if result.id != offered.id:
            return f"result names finding {result.id!r}, expected {offered.id!r}"
        if result.status not in STATUSES:
            return f"status {result.status!r} is not one of {list(STATUSES)}"
        for side in ("before", "after"):
            allowed = {_key(r) for r in getattr(offered, side)}
            extras = [_key(r) for r in getattr(result, side) if _key(r) not in allowed]
            if extras:
                return f"refs outside the offered {side} candidates: {extras}"
        if result.status == "unresolved":
            if ({_key(r) for r in result.before} != {_key(r) for r in offered.before} or
                {_key(r) for r in result.after} != {_key(r) for r in offered.after}):
                return "an unresolved finding must keep every candidate ref"
        elif result.method != "llm" or not result.review_required or not result.before + result.after:
            return "an adjudicated finding must be method=llm, reviewable and cite a clause"
        invalid = _domain_verify(result.citations, self.clauses).invalid
        if invalid:
            return f"{len(invalid)} citations do not verify against the source clauses"
        cited_bases = {_base(c.clause_id) for c in result.citations}
        for number in _CLAUSE_NUMBER.findall(result.reason):
            if not any(base == number or base.startswith(number + ".") for base in cited_bases):
                return f"reason mentions clause {number} absent from verified candidate/context evidence"
        return None

    def resolve_alignment(
        self, finding_id: str, before: list[ClauseRef | dict[str, Any]], after: list[ClauseRef | dict[str, Any]], status: str, reason: str,
    ) -> dict[str, Any]:
        before = [ClauseRef.model_validate(ref) for ref in before]
        after = [ClauseRef.model_validate(ref) for ref in after]
        with self._lock:
            offered = self.offered.get(finding_id)
            current = self.findings.get(finding_id)
            if offered is None or current is None:
                raise ValueError(f"finding {finding_id!r} is not part of this run")
            if current.status != "unresolved" or current.method == "llm":
                raise ValueError("only currently unresolved findings can be resolved")
            if status == "unresolved":
                return {"accepted": True, "changed": False, "reason": "abstained; candidate refs remain unresolved",
                        "finding": current.model_dump(mode="json")}
            unread = [f"{r.doc}:{r.clause_id}" for r in before + after if not self._fully_read(r)]
            if unread:
                raise ValueError(f"read complete source text before resolving candidates: {unread}")
            proposed = _domain_resolve(offered.model_copy(deep=True), self.clauses,
                                       before=before, after=after, status=status, reason=reason)
            if proposed.method == "llm":
                proposed = proposed.model_copy(update={
                    "citations": cite_context(proposed.before + proposed.after, clause_index(self.clauses),
                                              {(u.doc, u.unit_id): u for u in self.units}),
                })
            problem = self._decision_problem(offered, proposed)
            if proposed.method != "llm" and problem is None:
                problem = "domain resolver rejected the proposed status/refs"
            if problem:
                self.warnings.append(f"{finding_id}: adjudication rejected: {problem}.")
                return {"accepted": False, "reason": problem, "finding": current.model_dump(mode="json")}

            # Work on a copy: a transfer must not leave a stale added/missing
            # row, steal a resolved match, or drop an exclusively covered ref.
            candidate = dict(self.findings)
            candidate[finding_id] = proposed
            transferred = {_key(r) for r in (*proposed.before, *proposed.after)}
            for fid, donor in list(candidate.items()):
                if fid == finding_id:
                    continue
                shared = transferred & {_key(r) for r in (*donor.before, *donor.after)}
                if not shared:
                    continue
                if donor.status not in ("unresolved", "added", "missing") or donor.method == "llm":
                    problem = f"candidate ref already belongs to resolved finding {fid}"
                    break
                if donor.status in ("added", "missing") and len(donor.before + donor.after) != 1:
                    problem = f"finding {fid} cannot be transferred atomically"
                    break
                remaining_b = [r for r in donor.before if _key(r) not in shared]
                remaining_a = [r for r in donor.after if _key(r) not in shared]
                if not remaining_b and not remaining_a:
                    del candidate[fid]
                elif donor.status in ("added", "missing"):
                    problem = f"finding {fid} would retain a stale added/missing claim"
                    break
                else:
                    candidate[fid] = donor.model_copy(update={
                        "before": remaining_b, "after": remaining_a,
                        "citations": cite_context(remaining_b + remaining_a, clause_index(self.clauses),
                                                  {(u.doc, u.unit_id): u for u in self.units}),
                        "reason": donor.reason + " [Часть кандидатов передана подтверждённому соответствию.]",
                        "review_required": True,
                    })
            else:
                old_covered = {_key(r) for f in self.findings.values() for r in (*f.before, *f.after)}
                new_covered = {_key(r) for f in candidate.values() for r in (*f.before, *f.after)}
                if not old_covered <= new_covered:
                    problem = f"transfer would leave refs uncovered: {sorted(old_covered - new_covered)}"
            if problem:
                self.warnings.append(f"{finding_id}: adjudication rejected: {problem}.")
                return {"accepted": False, "reason": problem, "finding": current.model_dump(mode="json")}
            removed = sorted(set(self.findings) - set(candidate))
            self.findings = candidate
            for fid in list(self.offered):
                if fid not in candidate:
                    del self.offered[fid]
                elif fid != finding_id and self.offered[fid] != candidate[fid]:
                    self.offered[fid] = candidate[fid].model_copy(deep=True)
            self.last_report = None
            return {"accepted": True, "transferred_finding_ids": removed,
                    "finding": proposed.model_dump(mode="json")}

    def propose_unit_change(self, change: UnitChange | dict[str, Any]) -> dict[str, Any]:
        change = UnitChange.model_validate(change)
        with self._lock:
            if change.method != "llm" or not change.review_required:
                return {"accepted": False, "reason": "model proposal must be method=llm and review_required"}
            reviewed = (change.status == "created" and len(change.after) == 1 and
                        _unit_key(change.after[0]) in self._predecessor_searches)
            problem = validate_unit_change(change, self.documents, self.clauses, self.units,
                                           reviewed_predecessors=reviewed)
            if problem:
                self.warnings.append(f"Unit change {change.id} rejected: {problem}.")
                return {"accepted": False, "reason": problem}
            names = ", ".join(self._unit(ref).name for ref in change.before + change.after)
            change = change.model_copy(update={"reason":
                f"Предложение модели: «{change.status}» для подразделений {names}. "
                + ("Идентичность не подтверждена. " if change.status == "unresolved" else "")
                + "Основание — приведённые источники; требуется проверка."
            })
            covered = {_unit_key(u) for u in change.before + change.after}
            replaced: list[str] = []
            retained: list[UnitChange] = []
            for existing in self.unit_changes:
                refs = {_unit_key(u) for u in existing.before + existing.after}
                if not refs & covered:
                    retained.append(existing)
                    continue
                if existing.status != "unresolved" or not refs <= covered:
                    return {"accepted": False, "reason": f"unit refs already claimed by {existing.id}; "
                            "cannot replace a resolved or partially overlapping change"}
                replaced.append(existing.id)
            if any(row.id == change.id for row in retained):
                return {"accepted": False, "reason": f"unit change ID {change.id!r} belongs to a different result"}
            self.unit_changes = [*retained, change]
            self.last_report = None
            return {"accepted": True, "replaced_unresolved_ids": replaced,
                    "unit_change": change.model_dump(mode="json")}

    def propose_risk(self, risk: Risk | dict[str, Any]) -> dict[str, Any]:
        risk = Risk.model_validate(risk)
        with self._lock:
            if any(row.id == risk.id for row in self.risks):
                return {"accepted": False, "reason": f"risk ID {risk.id!r} already exists"}
            if risk.method != "llm":
                return {"accepted": False, "reason": "model proposal must be method=llm"}
            problem = validate_risk(risk, self.documents, self.clauses, self.units)
            if problem:
                self.warnings.append(f"Risk {risk.id} rejected: {problem}.")
                return {"accepted": False, "reason": problem}
            names = ", ".join(self._unit(ref).name for ref in risk.units)
            duties = "; ".join(self._clause(ref).text for ref in risk.refs)
            label = "возможное дублирование" if risk.kind == "potential_duplication" else "потенциальный конфликт интересов"
            risk = risk.model_copy(update={"reason":
                f"Предложение модели: {label}, ответственные — {names}. "
                f"Сопоставленные обязанности: {duties} Требуется проверка распределения полномочий."
            })
            signature = (risk.kind, frozenset(_key(ref) for ref in risk.refs))
            if any((row.kind, frozenset(_key(ref) for ref in row.refs)) == signature for row in self.risks):
                return {"accepted": False, "reason": "equivalent risk already exists in this run"}
            self.risks.append(risk)
            self.last_report = None
            return {"accepted": True, "risk": risk.model_dump(mode="json")}

    def verify_citations(self, citations: list[Citation | dict[str, Any]]) -> dict[str, Any]:
        return _domain_verify([Citation.model_validate(citation) for citation in citations], self.clauses).model_dump(mode="json")

    def _mentioned_ids(self, text: str) -> set[str]:
        ids = [*self.findings, *(r.id for r in self.unit_changes), *(r.id for r in self.risks)]
        shapes = {re.sub(r"\d+", lambda _m: r"\d+", re.escape(fid)) for fid in ids
                  if re.search(r"[^\W\d_]", fid)}
        if not shapes:
            return set()
        return set(re.findall(r"(?<![\w-])(?:" + "|".join(sorted(shapes)) + r")(?![\w-])", text))

    def _conclusion_problem(self, item: ConclusionItem, findings: dict[str, Finding]) -> str | None:
        if not item.text.strip():
            return "empty text"
        found = [findings.get(fid) for fid in item.finding_ids]
        changes = {change.id: change for change in self.unit_changes}
        risks = {risk.id: risk for risk in self.risks}
        if any(f is None for f in found) or any(uid not in changes for uid in item.unit_change_ids) or any(rid not in risks for rid in item.risk_ids):
            return "unknown finding, unit change or risk ID"
        if not (item.finding_ids or item.unit_change_ids or item.risk_ids):
            return "no referenced domain result IDs"
        listed = set(item.finding_ids + item.unit_change_ids + item.risk_ids)
        if self._mentioned_ids(item.text) - listed:
            return "text mentions domain result IDs not listed in the item's links"
        evidence = [c for f in found if f for c in f.citations]
        refs = [_key(ref) for f in found if f for ref in (*f.before, *f.after)]
        for uid in item.unit_change_ids:
            evidence.extend(changes[uid].citations)
        for rid in item.risk_ids:
            evidence.extend(risks[rid].citations)
            refs.extend(_key(ref) for ref in risks[rid].refs)
        bases = {_base(clause_id) for _, clause_id in [*refs, *(_key(c) for c in evidence)]}
        for number in _CLAUSE_NUMBER.findall(item.text):
            if not any(base == number or base.startswith(number + ".") for base in bases):
                return f"text mentions clause {number} absent from its linked results"
        for cite in item.citations:
            if _key(cite) not in refs and not any(_key(cite) == _key(c) and cite.quote in c.quote for c in evidence):
                return f"citation {cite.doc}:{cite.clause_id} is outside linked results"
        invalid = _domain_verify(item.citations, self.clauses).invalid
        if invalid:
            return f"{len(invalid)} citation(s) do not verify"
        return None

    def build(
        self, finding_ids: list[str], conclusion: list[ConclusionItem] | None = None,
    ) -> Report:
        unknown = [fid for fid in finding_ids if fid not in self.findings]
        if unknown:
            raise ValueError(f"finding IDs not part of this run: {unknown}")
        wanted = set(finding_ids)
        findings = [f for fid, f in self.findings.items() if fid in wanted]
        by_id = {f.id: f for f in findings}
        notes: list[str] = []
        accepted: list[ConclusionItem] | None = None
        if conclusion is not None:
            accepted = []
            for n, item in enumerate(conclusion, start=1):
                problem = self._conclusion_problem(item, by_id)
                if problem:
                    notes.append(f"Proposed conclusion item {n} dropped: {problem}.")
                    continue
                if not item.citations:
                    cites = [c for fid in item.finding_ids for c in by_id[fid].citations]
                    cites.extend(c for row in self.unit_changes if row.id in item.unit_change_ids for c in row.citations)
                    cites.extend(c for row in self.risks if row.id in item.risk_ids for c in row.citations)
                    item = item.model_copy(update={"citations": list({(_key(c), c.quote): c for c in cites}.values())})
                accepted.append(item)
            if not accepted:
                notes.append("No proposed conclusion item verified; deterministic conclusion used.")
                accepted = None
        with self._lock:
            report = _domain_build_report(
                self.run_id, self.documents, self.clauses, self.units, findings,
                mode="llm_assisted" if accepted or any(f.method == "llm" for f in findings)
                     or any(row.method == "llm" for row in [*self.unit_changes, *self.risks]) else "deterministic",
                conclusion=accepted,
                warnings=_dedupe([*self.base_warnings, *self.parse_warnings, *self.warnings, *notes]),
                unit_changes=self.unit_changes, risks=self.risks, agent=self.agent,
            )
        # Domain validation may reject proposed items or proposals once more.
        proposed_texts = {item.text for item in accepted or []}
        survived_prose = any(item.text in proposed_texts for item in report.conclusion)
        survived_decisions = any(row.method == "llm" for row in [*report.findings, *report.unit_changes, *report.risks])
        report = report.model_copy(update={
            "mode": "llm_assisted" if survived_prose or survived_decisions else "deterministic",
            "warnings": _dedupe(report.warnings),
        })
        self.last_report = report
        return report

    def build_report(self, finding_ids: list[str], conclusion: None = None) -> dict[str, Any]:
        if finding_ids and (len(set(finding_ids)) != len(finding_ids) or set(finding_ids) != set(self.findings)):
            raise ValueError("investigation finalizer must include every current finding ID exactly once; [] includes all")
        return self.build(list(self.findings), conclusion=None).model_dump(mode="json")


class _PageParams(BaseModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=8, ge=1, le=16)


class ListFindingsParams(_PageParams):
    statuses: list[str] | None = None


class InspectFindingsParams(BaseModel):
    finding_ids: list[str] = Field(min_length=1, max_length=8)
    ref_offset: int = Field(default=0, ge=0)
    ref_limit: int = Field(default=12, ge=1, le=16)


class ReadClausesParams(BaseModel):
    refs: list[ClauseRef] = Field(min_length=1, max_length=4)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=_PAGE_CHARS, ge=1, le=_PAGE_CHARS)


class SearchClausesParams(_PageParams):
    query: str = Field(min_length=2, max_length=180)
    edition: Literal["before", "after"] | None = None
    doc: str | None = None
    kind: Literal["function", "structure", "heading", "other"] | None = "function"
    limit: int = Field(default=6, ge=1, le=8)


class InspectUnitsParams(BaseModel):
    units: list[UnitRef] = Field(min_length=1, max_length=8)


class InspectDomainParams(_PageParams):
    kind: Literal["unit_changes", "risks"]
    limit: int = Field(default=6, ge=1, le=8)


class SearchUnitsParams(_PageParams):
    query: str | None = Field(default=None, max_length=180)
    edition: Literal["before", "after"] | None = None
    predecessor_for: UnitRef | None = None
    limit: int = Field(default=8, ge=1, le=12)


class OfferCandidatesParams(BaseModel):
    finding_id: str
    before: list[ClauseRef] = Field(default_factory=list, max_length=8)
    after: list[ClauseRef] = Field(default_factory=list, max_length=8)


class ResolveAlignmentParams(BaseModel):
    finding_id: str
    before: list[ClauseRef]
    after: list[ClauseRef]
    status: str
    reason: str = Field(min_length=1, max_length=1500)


class ProposeUnitChangeParams(BaseModel):
    change: UnitChange


class ProposeRiskParams(BaseModel):
    risk: Risk


class VerifyCitationsParams(BaseModel):
    citations: list[Citation] = Field(min_length=1, max_length=16)


class BuildReportParams(BaseModel):
    finding_ids: list[str] = Field(
        description="Use [] to include ALL current run findings, including unreviewed ones. "
        "A nonempty list must contain EVERY current finding ID exactly once; subsets are rejected."
    )
    conclusion: None = Field(default=None, description="Must be null: the domain builds a validated linked Russian conclusion.")


def create_audit_registry(context: AuditContext) -> ToolRegistry:
    """Fresh per-run registry; no parse/align, filesystem or network tool."""
    registry = ToolRegistry()
    specs = (
        ("list_findings", "Page through all current findings; filter by statuses including missing, duplicate and unresolved. Listing alone is not an investigation.", ListFindingsParams, context.list_findings),
        ("inspect_findings", "Inspect specific finding candidates, reasons and source citations; counts as inspected evidence.", InspectFindingsParams, context.inspect_findings),
        ("read_clauses", "Read exact source text by clause ref and character offset, with parent/role context; repeat with next_offset until complete.", ReadClausesParams, context.read_clauses),
        ("search_clauses", "Search within this run's before/after duties or structural clauses; returned excerpts and omission counts are evidence candidates only.", SearchClausesParams, context.search_clauses),
        ("inspect_units", "Read specific structural unit or role definitions and citations.", InspectUnitsParams, context.inspect_units),
        ("search_units", "Search all run-local units. predecessor_for=after UnitRef scans all before units before a created proposal.", SearchUnitsParams, context.search_units),
        ("inspect_domain", "Page current source-backed unit changes or risks before proposing another; returned citations are bounded excerpts.", InspectDomainParams, context.inspect_domain),
        ("offer_candidates", "Offer run-local inspected/searched function refs to an unresolved or unpaired finding; this never accepts a match.", OfferCandidatesParams, context.offer_candidates),
        ("resolve_alignment", "Adjudicate offered candidates only; a cross-finding transfer is atomic or explicitly rejected.", ResolveAlignmentParams, context.resolve_alignment),
        ("propose_unit_change", "Submit an evidenced structural unit change through the domain validator.", ProposeUnitChangeParams, context.propose_unit_change),
        ("propose_risk", "Submit an evidenced after-set overlap or potential conflict through the domain validator.", ProposeRiskParams, context.propose_risk),
        ("verify_citations", "Verify exact clause quotes against this run's preserved source text.", VerifyCitationsParams, context.verify_citations),
        ("build_report", "Finalize all current findings, validated unit changes and risks. Pass finding_ids=[] for the complete set and conclusion=null; prose is built deterministically.", BuildReportParams, context.build_report),
    )
    for name, description, params, fn in specs:
        registry.register(Tool(name=name, description=description, params=params, fn=partial(context.invoke, fn.__name__)))
    return registry
