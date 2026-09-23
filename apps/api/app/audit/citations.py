"""Citation construction and verification against preserved clause text."""

from __future__ import annotations

from .models import Citation, Clause, ClauseRef, InvalidCitation, VerifyResult

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
