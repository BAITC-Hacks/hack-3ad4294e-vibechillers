"""Pydantic wire models for the Function Lineage Auditor (docs/plan.md §3).

Field names and enums are the contract verbatim; do not rename them here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Edition = Literal["before", "after"]
ClauseKind = Literal["heading", "function", "structure", "other"]
UnitKind = Literal["unit", "role"]
FindingStatus = Literal["unchanged", "changed", "moved", "added", "missing", "duplicate", "unresolved"]
FindingMethod = Literal["exact", "lexical", "llm", "human"]
ReportMode = Literal["deterministic", "llm_assisted"]

FINDING_STATUSES: tuple[str, ...] = ("unchanged", "changed", "moved", "added", "missing", "duplicate", "unresolved")


class Document(BaseModel):
    doc: str
    doc_id: str
    sha256: str
    edition: Edition
    source: str


class Citation(BaseModel):
    doc: str
    clause_id: str
    quote: str


class ClauseRef(BaseModel):
    doc: str
    clause_id: str


class Clause(BaseModel):
    doc: str
    clause_id: str
    label: str
    parent_id: str | None
    text: str
    ordinal: int
    kind: ClauseKind
    unit_ids: list[str] = Field(default_factory=list)


class Unit(BaseModel):
    doc: str
    unit_id: str
    name: str
    kind: UnitKind
    parent_unit_id: str | None
    citations: list[Citation] = Field(default_factory=list)


class Finding(BaseModel):
    id: str
    status: FindingStatus
    before: list[ClauseRef] = Field(default_factory=list)
    after: list[ClauseRef] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    reason: str
    method: FindingMethod
    review_required: bool


class ConclusionItem(BaseModel):
    text: str
    finding_ids: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class Coverage(BaseModel):
    before_total: int
    after_total: int
    before_accounted: int
    after_accounted: int
    unresolved: int


class Report(BaseModel):
    run_id: str
    mode: ReportMode
    documents: list[Document]
    clauses: list[Clause]
    units: list[Unit]
    findings: list[Finding]
    conclusion: list[ConclusionItem]
    coverage: Coverage
    warnings: list[str] = Field(default_factory=list)


class ParseResult(BaseModel):
    """Output of the `parse_regulations` tool."""

    clauses: list[Clause] = Field(default_factory=list)
    units: list[Unit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class InvalidCitation(BaseModel):
    citation: Citation
    reason: str


class VerifyResult(BaseModel):
    """Output of the `verify_citations` tool."""

    valid: list[Citation] = Field(default_factory=list)
    invalid: list[InvalidCitation] = Field(default_factory=list)
