"""Function Lineage Auditor domain package (docs/plan.md §3).

Deterministic, keyless comparison of before/after regulation sets. API and agent
layers import from here and must not re-implement domain logic.

Public API
----------
Models (pydantic, contract field names verbatim):
    Document, Citation, ClauseRef, Clause, Unit, Finding, ConclusionItem, Coverage,
    Report, ParseResult{clauses, units, warnings}, InvalidCitation{citation, reason},
    VerifyResult{valid, invalid}; Literal aliases Edition, ClauseKind, UnitKind,
    FindingStatus, FindingMethod, ReportMode; FINDING_STATUSES tuple.

Documents:
    load_manifest(path=None) -> list[dict]
        Case manifest (default ``seeds/kt/manifest.json``); ``[]`` when absent.
    make_documents(before, after, manifest=None) -> (list[Document], list[str])
        ``before``/``after`` are ``(doc_id, sha256_full_hex, source_name)`` tuples. Alias is the manifest
        file stem (``v8``) on a SHA-256 match, else ``before-1``/``after-1``; warnings flag identical files
        and two exports of one source document.

Parsing (input = ``ParsedDoc.pages``, ``[{"page": int, "text": str}]``):
    parse_document(document, pages) -> ParseResult
    parse_documents(documents, pages_by_doc: dict[alias, pages]) -> ParseResult

Alignment and evidence:
    align_functions(clauses, units, before_docs, after_docs) -> list[Finding]
        Deterministic exact → lexical matching; every function clause lands in ≥1 finding.
    verify_citations(citations, clauses) -> VerifyResult
    resolve_alignment(finding, clauses, *, before, after, status, reason) -> Finding
        Validates an LLM adjudication against the finding's own candidate refs; rejected → original kept.

Report:
    compute_coverage(clauses, findings, before_docs, after_docs) -> Coverage
    deterministic_conclusion(findings, coverage, documents) -> list[ConclusionItem]
    build_report(run_id, documents, clauses, units, findings, *, mode="deterministic",
                 conclusion=None, warnings=None) -> Report
        Re-verifies every quote, guarantees coverage, builds/validates the conclusion.
    run_deterministic_audit(run_id, documents, pages_by_doc, warnings=None) -> Report
    report_summary(report) -> str   (text for ``final.data.text``)
"""

from .align import align_functions
from .citations import verify_citations
from .documents import DEFAULT_MANIFEST_PATH, load_manifest, make_documents
from .models import (
    FINDING_STATUSES,
    Citation,
    Clause,
    ClauseKind,
    ClauseRef,
    ConclusionItem,
    Coverage,
    Document,
    Edition,
    Finding,
    FindingMethod,
    FindingStatus,
    InvalidCitation,
    ParseResult,
    Report,
    ReportMode,
    Unit,
    UnitKind,
    VerifyResult,
)
from .parser import parse_document, parse_documents
from .report import (
    build_report,
    compute_coverage,
    deterministic_conclusion,
    report_summary,
    resolve_alignment,
    run_deterministic_audit,
)

__all__ = [
    "FINDING_STATUSES",
    "DEFAULT_MANIFEST_PATH",
    "Citation",
    "Clause",
    "ClauseKind",
    "ClauseRef",
    "ConclusionItem",
    "Coverage",
    "Document",
    "Edition",
    "Finding",
    "FindingMethod",
    "FindingStatus",
    "InvalidCitation",
    "ParseResult",
    "Report",
    "ReportMode",
    "Unit",
    "UnitKind",
    "VerifyResult",
    "align_functions",
    "build_report",
    "compute_coverage",
    "deterministic_conclusion",
    "load_manifest",
    "make_documents",
    "parse_document",
    "parse_documents",
    "report_summary",
    "resolve_alignment",
    "run_deterministic_audit",
    "verify_citations",
]
