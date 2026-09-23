"""Citation construction and verification against preserved clause text."""

from __future__ import annotations

from .models import Citation, Clause, ClauseRef, InvalidCitation, Unit, VerifyResult

_QUOTE_LIMIT = 240


def clause_index(clauses: list[Clause]) -> dict[tuple[str, str], Clause]:
    return {(c.doc, c.clause_id): c for c in clauses}


def quote_for(clause: Clause, limit: int = _QUOTE_LIMIT) -> str:
    """An exact substring of the clause text: the whole text, or its head cut at a word boundary."""
    text = clause.text
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit)
    return text[: cut if cut > limit // 2 else limit].rstrip()


def cite(clause: Clause) -> Citation | None:
    quote = quote_for(clause)
    if not quote:
        return None
    return Citation(doc=clause.doc, clause_id=clause.clause_id, quote=quote)


def cite_refs(refs: list[ClauseRef], index: dict[tuple[str, str], Clause]) -> list[Citation]:
    out: list[Citation] = []
    for ref in refs:
        clause = index.get((ref.doc, ref.clause_id))
        citation = cite(clause) if clause is not None else None
        if citation is not None:
            out.append(citation)
    return out


def cite_context(
    refs: list[ClauseRef],
    index: dict[tuple[str, str], Clause],
    units: dict[tuple[str, str], Unit] | None = None,
) -> list[Citation]:
    """Cite candidate text, ancestors and associated definitions without changing candidate refs."""
    evidence = cite_refs(refs, index)
    by_unit = units if units is not None else {}
    visited: set[tuple[str, str]] = set()
    for ref in refs:
        clause = index.get((ref.doc, ref.clause_id))
        while clause is not None and (clause.doc, clause.clause_id) not in visited:
            visited.add((clause.doc, clause.clause_id))
            # Parent qualifications can occur after the leading excerpt. Cite
            # their complete source text, never a head that omits a prohibition.
            citation = (
                cite(clause) if clause.clause_id == ref.clause_id
                else Citation(doc=clause.doc, clause_id=clause.clause_id, quote=clause.text)
                if clause.text else None
            )
            if citation is not None:
                evidence.append(citation)
            for uid in clause.unit_ids:
                unit = by_unit.get((clause.doc, uid))
                if unit is not None:
                    for source_citation in unit.citations:
                        if check_citation(source_citation, index) is not None:
                            continue
                        evidence.append(source_citation)
                        source = index[(source_citation.doc, source_citation.clause_id)]
                        if unit.kind == "role" and not source.label:
                            evidence.append(Citation(doc=source.doc, clause_id=source.clause_id, quote=source.text))
            clause = index.get((clause.doc, clause.parent_id)) if clause.parent_id else None
    return list({(c.doc, c.clause_id, c.quote): c for c in evidence}.values())


def check_citation(citation: Citation, index: dict[tuple[str, str], Clause]) -> str | None:
    """None when valid, otherwise the reason it is invalid."""
    clause = index.get((citation.doc, citation.clause_id))
    if clause is None:
        return f"clause {citation.doc}:{citation.clause_id} does not exist in this run"
    if not citation.quote:
        return "quote is empty"
    if citation.quote not in clause.text:
        return f"quote is not an exact substring of {citation.doc}:{citation.clause_id}"
    return None


def verify_citations(citations: list[Citation], clauses: list[Clause]) -> VerifyResult:
    """Split citations into those whose quote occurs verbatim in the named clause and the rest."""
    index = clause_index(clauses)
    result = VerifyResult()
    for citation in citations:
        reason = check_citation(citation, index)
        if reason is None:
            result.valid.append(citation)
        else:
            result.invalid.append(InvalidCitation(citation=citation, reason=reason))
    return result
