"""Run-scoped audit tools for the typed :class:`ToolRegistry`.

One :class:`AuditContext` holds a single audit run in memory: its documents,
the ingested page text, parsed clauses/units and the current findings. The
five tools created by :func:`create_audit_registry` close over that context
only, so a caller (or a model) can name documents by their report-local alias
and never by a filesystem path.

All domain work is delegated to :mod:`app.audit`; this module adds the scoping
and the guards around model-proposed input:

- ``resolve_alignment`` accepts adjudication only for originally ambiguous
  (``unresolved``) findings and only within that finding's offered candidate
  refs; any result that violates this keeps the finding unresolved.
- ``build_report`` accepts proposed conclusion items only when every finding ID
  and clause number they mention, and every citation they carry, is verified
  against this run; otherwise the item is dropped with a warning.
"""

from __future__ import annotations

import re
import threading
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from ..audit import (
    FINDING_STATUSES,
    Citation,
    Clause,
    ClauseRef,
    ConclusionItem,
    Document,
    Finding,
    Report,
    Unit,
)
from ..audit import align_functions as _domain_align
from ..audit import build_report as _domain_build_report
from ..audit import parse_documents as _domain_parse
from ..audit import resolve_alignment as _domain_resolve
from ..audit import verify_citations as _domain_verify
from .tools import Tool, ToolRegistry

__all__ = [
    "AUDIT_TOOL_NAMES",
    "AuditContext",
    "create_audit_registry",
]

AUDIT_TOOL_NAMES = (
    "parse_regulations",
    "align_functions",
    "resolve_alignment",
    "verify_citations",
    "build_report",
)
STATUSES: tuple[str, ...] = FINDING_STATUSES

# Dotted clause numbers ("3.10", "2.4.1") mentioned in prose. Dates such as
# 25.06.2021 do not match: the lookarounds reject a neighbouring digit/dot.
_CLAUSE_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3})+)(?!\.?\d)(?!\w)")


def _ref_key(ref: ClauseRef | Citation) -> tuple[str, str]:
    return (ref.doc, ref.clause_id)


def _clause_base(clause_id: str) -> str:
    """Numeric path of a clause ID: ``2.3.1/а@2`` -> ``2.3.1``."""
    return clause_id.split("/", 1)[0].split("@", 1)[0]


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


class AuditContext:
    """In-memory state of exactly one audit run; the tools' only data source."""

    def __init__(
        self,
        run_id: str,
        documents: list[Document],
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
        self.warnings: list[str] = []  # guard/adjudication notes added during the run
        self.clauses_by_doc: dict[str, list[Clause]] = {}
        self.units_by_doc: dict[str, list[Unit]] = {}
        self.findings: dict[str, Finding] = {}  # current state, deterministic order
        self.offered: dict[str, Finding] = {}  # deterministic candidates, never mutated
        self.last_report: Report | None = None
        self._lock = threading.Lock()

    @classmethod
    def from_report(
        cls,
        report: Report,
        pages_by_doc: dict[str, list[dict[str, Any]]] | None = None,
    ) -> AuditContext:
        """Rebuild a context from a finished report (e.g. for LLM adjudication)."""
        ctx = cls(report.run_id, report.documents, pages_by_doc, report.warnings)
        for doc in ctx.documents:
            ctx.clauses_by_doc[doc.doc] = [c for c in report.clauses if c.doc == doc.doc]
            ctx.units_by_doc[doc.doc] = [u for u in report.units if u.doc == doc.doc]
        ctx._set_findings(report.findings)
        return ctx

    # -- views -------------------------------------------------------------

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
        known = ", ".join(d.doc for d in self.documents) or "<none>"
        raise ValueError(f"document {alias!r} is not part of this run; known documents: [{known}]")

    def _set_findings(self, findings: list[Finding]) -> None:
        ids = [f.id for f in findings]
        if len(set(ids)) != len(ids):
            raise ValueError("finding IDs must be unique within a run")
        self.findings = {f.id: f for f in findings}
        self.offered = {f.id: f.model_copy(deep=True) for f in findings}

    # -- tools -------------------------------------------------------------

    def parse_regulations(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        docs = [Document.model_validate(d) for d in documents]
        if not docs:
            raise ValueError("documents must name at least one document of this run")
        for doc in docs:
            if self._document(doc.doc) != doc:
                raise ValueError(
                    f"document {doc.doc!r} does not match this run's record "
                    "(doc_id, sha256, edition and source must be identical)"
                )
            if doc.doc not in self._pages:
                raise ValueError(f"source text of document {doc.doc!r} is not held in this run")
        with self._lock:
            result = _domain_parse(docs, {d.doc: self._pages[d.doc] for d in docs})
            for doc in docs:
                self.clauses_by_doc[doc.doc] = [c for c in result.clauses if c.doc == doc.doc]
                self.units_by_doc[doc.doc] = [u for u in result.units if u.doc == doc.doc]
            self.parse_warnings = _dedupe([*self.parse_warnings, *result.warnings])
            # Clauses changed: earlier findings no longer describe this parse.
            self._set_findings([])
        return result.model_dump(mode="json")

    def align_functions(self, before_docs: list[str], after_docs: list[str]) -> dict[str, Any]:
        if not before_docs or not after_docs:
            raise ValueError("align_functions needs at least one before and one after document")
        if set(before_docs) & set(after_docs):
            raise ValueError("a document cannot be on both sides of the comparison")
        for side, aliases in (("before", before_docs), ("after", after_docs)):
            for alias in aliases:
                doc = self._document(alias)
                if doc.edition != side:
                    raise ValueError(f"document {alias!r} is a {doc.edition!r} edition, not {side!r}")
                if alias not in self.clauses_by_doc:
                    raise ValueError(f"document {alias!r} is not parsed yet; call parse_regulations first")
        chosen = set(before_docs) | set(after_docs)
        with self._lock:
            findings = _domain_align(
                [c for c in self.clauses if c.doc in chosen],
                [u for u in self.units if u.doc in chosen],
                list(before_docs),
                list(after_docs),
            )
            self._set_findings(findings)
        return {"findings": [f.model_dump(mode="json") for f in findings]}

    def resolve_alignment(
        self,
        finding_id: str,
        before: list[dict[str, Any]],
        after: list[dict[str, Any]],
        status: str,
        reason: str,
    ) -> dict[str, Any]:
        offered = self.offered.get(finding_id)
        if offered is None:
            raise ValueError(f"finding {finding_id!r} is not part of this run")
        if offered.status != "unresolved":
            raise ValueError(
                f"finding {finding_id!r} is not ambiguous (deterministic status "
                f"{offered.status!r}); only unresolved findings can be adjudicated"
            )
        before_refs = [ClauseRef.model_validate(r) for r in before]
        after_refs = [ClauseRef.model_validate(r) for r in after]
        with self._lock:
            try:
                proposed = _domain_resolve(
                    offered.model_copy(deep=True),
                    self.clauses,
                    before=before_refs,
                    after=after_refs,
                    status=status,
                    reason=reason,
                )
                problem = self._decision_problem(offered, proposed)
            except (ValueError, ValidationError) as exc:
                proposed, problem = None, f"{type(exc).__name__}: {exc}"
            if problem is not None:
                proposed = offered.model_copy(
                    update={
                        "status": "unresolved",
                        "reason": f"{offered.reason} [adjudication rejected: {problem}]",
                        "review_required": True,
                    },
                    deep=True,
                )
            self.findings[finding_id] = proposed
        return {"finding": proposed.model_dump(mode="json")}

    def verify_citations(self, citations: list[dict[str, Any]]) -> dict[str, Any]:
        cites = [Citation.model_validate(c) for c in citations]
        return _domain_verify(cites, self.clauses).model_dump(mode="json")

    def build_report(
        self,
        finding_ids: list[str],
        conclusion: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self.build(finding_ids, conclusion).model_dump(mode="json")

    # -- guards ------------------------------------------------------------

    def _decision_problem(self, offered: Finding, result: Finding) -> str | None:
        """Why a resolved finding must not be published, or None when it is sound.

        Post-condition over the domain resolver: the result may only narrow the
        offered candidates, use a contract status, stay reviewable, and carry
        citations that verify against this run's clauses.
        """
        if result.id != offered.id:
            return f"result names finding {result.id!r}, expected {offered.id!r}"
        if result.status not in STATUSES:
            return f"status {result.status!r} is not one of {list(STATUSES)}"
        offered_before = {_ref_key(r) for r in offered.before}
        offered_after = {_ref_key(r) for r in offered.after}
        extra = [k for k in (_ref_key(r) for r in result.before) if k not in offered_before]
        extra += [k for k in (_ref_key(r) for r in result.after) if k not in offered_after]
        if extra:
            return f"refs outside the offered candidates: {extra}"
        if result.status == "unresolved":
            kept = {_ref_key(r) for r in result.before} == offered_before and {
                _ref_key(r) for r in result.after
            } == offered_after
            if not kept:
                return "an unresolved finding must keep every candidate ref"
        else:
            if result.method != "llm" or not result.review_required:
                return "an adjudicated finding must be method=llm and review_required"
            if not result.before and not result.after:
                return "an adjudicated finding must reference at least one clause"
        if result.citations:
            verdict = _domain_verify(result.citations, self.clauses)
            if verdict.invalid:
                return f"{len(verdict.invalid)} citation(s) do not verify against the source clauses"
        return None

    def _conclusion_problem(self, item: ConclusionItem, findings: dict[str, Finding]) -> str | None:
        """Why a proposed conclusion item must be dropped, or None when every reference verifies."""
        if not item.text.strip():
            return "empty text"
        if not item.finding_ids:
            return "no finding_ids"
        unknown = [fid for fid in item.finding_ids if fid not in findings]
        if unknown:
            return f"unknown finding IDs {unknown}"
        mentioned = self._mentioned_finding_ids(item.text)
        unlisted = sorted(m for m in mentioned if m not in item.finding_ids)
        if unlisted:
            return f"text mentions finding IDs not listed in finding_ids: {unlisted}"
        referenced = [findings[fid] for fid in item.finding_ids]
        allowed_refs = {
            _ref_key(r)
            for f in referenced
            for r in (*f.before, *f.after, *f.citations)
        }
        stray = [_ref_key(c) for c in item.citations if _ref_key(c) not in allowed_refs]
        if stray:
            return f"citations outside the referenced findings: {stray}"
        if item.citations:
            verdict = _domain_verify(item.citations, self.clauses)
            if verdict.invalid:
                reasons = "; ".join(f"{i.citation.doc}/{i.citation.clause_id}: {i.reason}" for i in verdict.invalid)
                return f"citations do not verify ({reasons})"
        bases = {_clause_base(cid) for _, cid in allowed_refs}
        for number in _CLAUSE_NUMBER.findall(item.text):
            if not any(b == number or b.startswith(number + ".") for b in bases):
                return f"text mentions clause {number} that none of its findings reference"
        return None

    def _mentioned_finding_ids(self, text: str) -> set[str]:
        """Finding-ID-shaped tokens in prose, using the shapes of this run's IDs."""
        ids = list(self.offered) or list(self.findings)
        shapes = set()
        for fid in ids:
            shape = re.sub(r"\d+", lambda _m: r"\d+", re.escape(fid))
            if re.search(r"[^\W\d_]", fid):  # an all-digit shape would match any number
                shapes.add(shape)
        if not shapes:
            return set()
        pattern = re.compile(r"(?<![\w-])(?:" + "|".join(sorted(shapes)) + r")(?![\w-])")
        return set(pattern.findall(text))

    # -- report ------------------------------------------------------------

    def build(
        self,
        finding_ids: list[str],
        conclusion: list[dict[str, Any]] | list[ConclusionItem] | None = None,
    ) -> Report:
        unknown = [fid for fid in finding_ids if fid not in self.findings]
        if unknown:
            raise ValueError(f"finding IDs not part of this run: {unknown}")
        wanted = set(finding_ids)
        findings = [f for fid, f in self.findings.items() if fid in wanted]
        by_id = {f.id: f for f in findings}
        warnings: list[str] = []

        accepted: list[ConclusionItem] | None = None
        if conclusion is not None:
            accepted = []
            for n, raw in enumerate(conclusion, start=1):
                item = raw if isinstance(raw, ConclusionItem) else ConclusionItem.model_validate(raw)
                problem = self._conclusion_problem(item, by_id)
                if problem is not None:
                    warnings.append(f"Proposed conclusion item {n} dropped: {problem}.")
                    continue
                if not item.citations:  # attach the referenced findings' verified evidence
                    cites = {(_ref_key(c), c.quote): c for fid in item.finding_ids for c in by_id[fid].citations}
                    item = item.model_copy(update={"citations": list(cites.values())})
                accepted.append(item)
            if not accepted:
                warnings.append("No proposed conclusion item verified; the deterministic conclusion is used.")
                accepted = None

        llm_findings = any(f.method == "llm" for f in findings)
        with self._lock:
            report = _domain_build_report(
                self.run_id,
                self.documents,
                self.clauses,
                self.units,
                findings,
                mode="llm_assisted" if (accepted or llm_findings) else "deterministic",
                conclusion=accepted,
                warnings=_dedupe([*self.base_warnings, *self.parse_warnings, *self.warnings, *warnings]),
            )
        # The domain re-verifies and may still drop items; only surviving model prose counts.
        proposed_texts = {i.text for i in accepted or []}
        llm_prose = any(i.text in proposed_texts for i in report.conclusion)
        mode = "llm_assisted" if (llm_prose or llm_findings) else "deterministic"
        report = report.model_copy(update={"mode": mode, "warnings": _dedupe(report.warnings)})
        self.last_report = report
        return report


# -- typed tool parameters ---------------------------------------------------


class ParseRegulationsParams(BaseModel):
    documents: list[Document] = Field(
        description="Documents of this run to parse, exactly as listed in the run's documents."
    )


class AlignFunctionsParams(BaseModel):
    before_docs: list[str] = Field(description="Aliases of this run's before-edition documents.")
    after_docs: list[str] = Field(description="Aliases of this run's after-edition documents.")


class ResolveAlignmentParams(BaseModel):
    finding_id: str = Field(description="ID of an unresolved finding of this run.")
    before: list[ClauseRef] = Field(description="Chosen subset of the finding's offered before refs.")
    after: list[ClauseRef] = Field(description="Chosen subset of the finding's offered after refs.")
    status: str = Field(description=f"One of {', '.join(STATUSES)}; choose unresolved when unsure.")
    reason: str = Field(min_length=1, description="Short justification grounded in the clause texts.")


class VerifyCitationsParams(BaseModel):
    citations: list[Citation] = Field(description="Citations to check against this run's clauses.")


class BuildReportParams(BaseModel):
    finding_ids: list[str] = Field(description="IDs of this run's findings to include.")
    conclusion: list[ConclusionItem] | None = Field(
        default=None,
        description="Proposed conclusion; null uses the deterministic conclusion.",
    )


def create_audit_registry(context: AuditContext) -> ToolRegistry:
    """A fresh registry holding exactly the five audit tools, scoped to `context`."""
    registry = ToolRegistry()
    specs = (
        (
            "parse_regulations",
            "Parse this run's regulation documents into numbered clauses and units.",
            ParseRegulationsParams,
            context.parse_regulations,
        ),
        (
            "align_functions",
            "Deterministically align function clauses of before documents to after documents.",
            AlignFunctionsParams,
            context.align_functions,
        ),
        (
            "resolve_alignment",
            "Propose a decision for one unresolved finding using only its offered candidate refs; "
            "invalid proposals leave the finding unresolved.",
            ResolveAlignmentParams,
            context.resolve_alignment,
        ),
        (
            "verify_citations",
            "Check that each quote is an exact substring of the named clause in this run.",
            VerifyCitationsParams,
            context.verify_citations,
        ),
        (
            "build_report",
            "Build the audit report from findings; proposed conclusion items must reference "
            "verified findings and citations.",
            BuildReportParams,
            context.build_report,
        ),
    )
    for name, description, params, fn in specs:
        registry.register(Tool(name=name, description=description, params=params, fn=fn))
    return registry
