"""Report assembly: evidence re-verification, coverage, conclusion, LLM-proposal validation."""

from __future__ import annotations

from .align import align_functions
from .citations import check_citation, cite_context, cite_refs, clause_index
from .models import (
    FINDING_STATUSES,
    Citation,
    Clause,
    ClauseRef,
    ConclusionItem,
    Coverage,
    Document,
    Finding,
    Report,
    Unit,
)
from .parser import parse_documents

_STATUS_ORDER = ("missing", "duplicate", "added", "unresolved", "changed", "moved", "unchanged")
_LIST_LIMIT = 15


def _key(ref: ClauseRef | Citation) -> tuple[str, str]:
    return (ref.doc, ref.clause_id)


def _function_refs(clauses: list[Clause], docs: list[str]) -> set[tuple[str, str]]:
    wanted = set(docs)
    return {(c.doc, c.clause_id) for c in clauses if c.kind == "function" and c.doc in wanted}


def _editions(documents: list[Document]) -> tuple[list[str], list[str]]:
    before = [d.doc for d in documents if d.edition == "before"]
    after = [d.doc for d in documents if d.edition == "after"]
    return before, after


def compute_coverage(clauses: list[Clause], findings: list[Finding], before_docs: list[str], after_docs: list[str]) -> Coverage:
    """Unique function refs per side and how many appear in findings; ``unresolved`` counts unique
    function refs (both sides) that appear in ``unresolved`` findings."""
    before_all = _function_refs(clauses, before_docs)
    after_all = _function_refs(clauses, after_docs)
    seen: set[tuple[str, str]] = set()
    unresolved: set[tuple[str, str]] = set()
    for finding in findings:
        refs = {_key(r) for r in finding.before + finding.after}
        seen |= refs
        if finding.status == "unresolved":
            unresolved |= refs & (before_all | after_all)
    return Coverage(
        before_total=len(before_all),
        after_total=len(after_all),
        before_accounted=len(before_all & seen),
        after_accounted=len(after_all & seen),
        unresolved=len(unresolved),
    )


def _anchor(finding: Finding) -> str:
    b = ", ".join(f"{r.doc}:{r.clause_id}" for r in finding.before)
    a = ", ".join(f"{r.doc}:{r.clause_id}" for r in finding.after)
    if b and a:
        return f"{finding.id} ({b} → {a})"
    return f"{finding.id} ({b or a})"


_TEMPLATES = {
    "missing": "Без подтверждённого преемника в новой редакции — {n}: {items}. Это не доказательство утраты "
               "функции, а сигнал для проверки экспертом.",
    "duplicate": "Возможное дублирование ответственности — {n}: {items}. Совпадение формулировок само по себе "
                 "дублированием не является; требуется проверка.",
    "added": "Новые функции без подтверждённого предшественника — {n}: {items}.",
    "unresolved": "Не разрешено автоматически — {n}: {items}. Все кандидаты сохранены для решения эксперта.",
    "changed": "Функции с изменённой формулировкой — {n}: {items}.",
    "moved": "Функции сохранены, но изменён номер пункта или владелец — {n}: {items}. Перенумерация не означает утрату.",
    "unchanged": "Без изменений — {n} функций.",
}


def deterministic_conclusion(findings: list[Finding], coverage: Coverage, documents: list[Document]) -> list[ConclusionItem]:
    """Templated conclusion: one item per non-empty status, each citing its findings' verified quotes."""
    items: list[ConclusionItem] = []
    for status in _STATUS_ORDER:
        group = [f for f in findings if f.status == status]
        if not group:
            continue
        shown = "; ".join(_anchor(f) for f in group[:_LIST_LIMIT])
        if len(group) > _LIST_LIMIT:
            shown += f"; и ещё {len(group) - _LIST_LIMIT}"
        citations: list[Citation] = []
        for finding in group:
            citations.extend(finding.citations)
        items.append(
            ConclusionItem(
                text=_TEMPLATES[status].format(n=len(group), items=shown),
                finding_ids=[f.id for f in group],
                citations=citations,
            )
        )
    return items


def _verify_findings(findings: list[Finding], index: dict, warnings: list[str]) -> list[Finding]:
    out: list[Finding] = []
    for finding in findings:
        before = [r for r in finding.before if _key(r) in index]
        after = [r for r in finding.after if _key(r) in index]
        if len(before) + len(after) < len(finding.before) + len(finding.after):
            warnings.append(f"{finding.id}: references to clauses absent from this run were removed.")
        valid: list[Citation] = []
        for citation in finding.citations:
            reason = check_citation(citation, index)
            if reason is None:
                valid.append(citation)
            else:
                warnings.append(f"{finding.id}: citation withheld — {reason}.")
        update: dict = {"before": before, "after": after, "citations": valid}
        cited_refs = {_key(c) for c in valid}
        required_refs = {_key(r) for r in finding.before + finding.after}
        if (not valid or not required_refs <= cited_refs) and finding.status != "unresolved":
            update.update(status="unresolved", review_required=True,
                          reason=finding.reason + " [Не все сопоставляемые пункты имеют проверенную цитату.]")
        out.append(finding.model_copy(update=update))
    return out


def _ensure_accounted(findings: list[Finding], clauses: list[Clause], index: dict, before_docs, after_docs,
                      warnings: list[str]) -> list[Finding]:
    seen = {_key(r) for f in findings for r in f.before + f.after}
    order = [c for c in clauses if c.kind == "function"]
    before_set, after_set = set(before_docs), set(after_docs)
    used_ids = {f.id for f in findings}
    n = len(findings)
    extra: list[Finding] = []
    for clause in order:
        if (clause.doc, clause.clause_id) in seen or clause.doc not in before_set | after_set:
            continue
        ref = ClauseRef(doc=clause.doc, clause_id=clause.clause_id)
        n += 1
        while f"F{n:03d}" in used_ids:
            n += 1
        used_ids.add(f"F{n:03d}")
        side_before = clause.doc in before_set
        extra.append(
            Finding(
                id=f"F{n:03d}", status="unresolved",
                before=[ref] if side_before else [], after=[] if side_before else [ref],
                citations=cite_refs([ref], index),
                reason="Пункт не вошёл ни в один вывод после выбора выводов; оставлен неразрешённым.",
                method="exact", review_required=True,
            )
        )
    if extra:
        warnings.append(f"{len(extra)} function clause(s) were not covered by the selected findings; added as unresolved.")
    return findings + extra


def _validate_conclusion(items: list[ConclusionItem], findings: list[Finding], index: dict,
                         warnings: list[str]) -> list[ConclusionItem]:
    by_id = {f.id: f for f in findings}
    out: list[ConclusionItem] = []
    for n, item in enumerate(items, start=1):
        ids = [fid for fid in item.finding_ids if fid in by_id]
        unknown = [fid for fid in item.finding_ids if fid not in by_id]
        if unknown:
            warnings.append(f"Conclusion item {n}: unknown finding ids dropped: {', '.join(unknown)}.")
        if not ids or not item.text.strip():
            warnings.append(f"Conclusion item {n} dropped: it does not reference a verified finding.")
            continue
        direct = {_key(r) for fid in ids for r in (*by_id[fid].before, *by_id[fid].after)}
        evidence = [c for fid in ids for c in by_id[fid].citations]
        citations: list[Citation] = []
        for citation in item.citations:
            reason = check_citation(citation, index)
            if reason is None and _key(citation) not in direct and not any(
                _key(citation) == _key(c) and citation.quote in c.quote for c in evidence
            ):
                reason = "citation does not belong to the referenced findings"
            if reason is None:
                citations.append(citation)
            else:
                warnings.append(f"Conclusion item {n}: citation withheld — {reason}.")
        if not citations:
            citations = [c for fid in ids for c in by_id[fid].citations]
        if not citations:
            warnings.append(f"Conclusion item {n} dropped: its findings carry no verified citation.")
            continue
        out.append(ConclusionItem(text=item.text, finding_ids=ids, citations=citations))
    return out


def build_report(
    run_id: str,
    documents: list[Document],
    clauses: list[Clause],
    units: list[Unit],
    findings: list[Finding],
    *,
    mode: str = "deterministic",
    conclusion: list[ConclusionItem] | None = None,
    warnings: list[str] | None = None,
) -> Report:
    """Assemble a ``Report``: re-verify every quote, guarantee function coverage, build or validate the conclusion.

    ``conclusion=None`` yields the deterministic templated conclusion. A proposed conclusion keeps only items
    that reference existing findings with verified citations; if none survive, the deterministic one is used.
    """
    notes = list(warnings or [])
    index = clause_index(clauses)
    before_docs, after_docs = _editions(documents)
    checked = _verify_findings(findings, index, notes)
    checked = _ensure_accounted(checked, clauses, index, before_docs, after_docs, notes)
    coverage = compute_coverage(clauses, checked, before_docs, after_docs)
    items: list[ConclusionItem] | None = None
    if conclusion is not None:
        items = _validate_conclusion(conclusion, checked, index, notes)
        if not items:
            notes.append("Proposed conclusion rejected: no item referenced verified findings; deterministic conclusion used.")
            items = None
    if items is None:
        items = deterministic_conclusion(checked, coverage, documents)
    return Report(
        run_id=run_id,
        mode=mode,
        documents=documents,
        clauses=clauses,
        units=units,
        findings=checked,
        conclusion=items,
        coverage=coverage,
        warnings=notes,
    )


_SHAPES = {
    "unchanged": (1, 1),
    "changed": (1, 1),
    "moved": (1, 1),
    "added": (0, 1),
    "missing": (1, 0),
    "duplicate": (1, 2),
    "unresolved": (0, 0),
}


def resolve_alignment(
    finding: Finding,
    clauses: list[Clause],
    *,
    before: list[ClauseRef],
    after: list[ClauseRef],
    status: str,
    reason: str,
) -> Finding:
    """Validate an adjudication proposed for `finding`.

    Accepted only when the refs are a subset of the finding's own candidate refs, the status is a contract
    status whose shape fits the refs, and a reason is given; the result is ``method=llm`` and always
    ``review_required``. Otherwise the original finding is returned unchanged apart from a rejection note.
    """
    index = clause_index(clauses)
    offered_b = {_key(r) for r in finding.before}
    offered_a = {_key(r) for r in finding.after}
    problem = None
    if status not in FINDING_STATUSES:
        problem = f"unknown status '{status}'"
    elif not reason.strip():
        problem = "no reason given"
    elif any(_key(r) not in offered_b for r in before) or any(_key(r) not in offered_a for r in after):
        problem = "refs outside the offered candidates"
    elif any(_key(r) not in index for r in before + after):
        problem = "refs to clauses absent from this run"
    else:
        need_b, need_a = _SHAPES[status]
        if len(before) < need_b or len(after) < need_a:
            problem = f"status '{status}' needs at least {need_b} before and {need_a} after refs"
        elif status == "added" and before:
            problem = "status 'added' cannot keep a predecessor"
        elif status == "missing" and after:
            problem = "status 'missing' cannot keep a successor"
    if problem is not None:
        return finding.model_copy(update={"reason": f"{finding.reason} [Предложение LLM отклонено: {problem}.]"})
    unique_b = list({_key(r): r for r in before}.values())
    unique_a = list({_key(r): r for r in after}.values())
    return Finding(
        id=finding.id,
        status=status,
        before=unique_b,
        after=unique_a,
        citations=cite_context(unique_b + unique_a, index),
        reason=f"Решение LLM (требует проверки): {reason.strip()}",
        method="llm",
        review_required=True,
    )


def report_summary(report: Report) -> str:
    """Plain-text rendering of the conclusion for ``final.data.text``."""
    lines = [item.text for item in report.conclusion]
    if report.warnings:
        lines.append(f"Предупреждений: {len(report.warnings)}.")
    return "\n".join(lines)


def run_deterministic_audit(
    run_id: str,
    documents: list[Document],
    pages_by_doc: dict[str, list[dict]],
    warnings: list[str] | None = None,
) -> Report:
    """Parse, align and assemble a keyless report in one call."""
    parsed = parse_documents(documents, pages_by_doc)
    before_docs, after_docs = _editions(documents)
    findings = align_functions(parsed.clauses, parsed.units, before_docs, after_docs)
    return build_report(
        run_id,
        documents,
        parsed.clauses,
        parsed.units,
        findings,
        mode="deterministic",
        warnings=list(warnings or []) + parsed.warnings,
    )
