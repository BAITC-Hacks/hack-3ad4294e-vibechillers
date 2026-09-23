"""Report assembly: evidence re-verification, coverage, conclusion, LLM-proposal validation."""

from __future__ import annotations

from .align import align_functions
from .citations import check_citation, cite_context, cite_refs, clause_index
from .lineage import analyze_domain, validate_risk, validate_unit_change
from .models import (
    FINDING_STATUSES,
    AgentExecution,
    Citation,
    Clause,
    ClauseRef,
    ConclusionItem,
    Coverage,
    Document,
    Finding,
    Report,
    Risk,
    Unit,
    UnitChange,
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


def _validate_conclusion(
    items: list[ConclusionItem], findings: list[Finding], index: dict,
    warnings: list[str], unit_changes: list[UnitChange], risks: list[Risk],
) -> list[ConclusionItem]:
    groups = (
        ("finding_ids", {f.id: f for f in findings}),
        ("unit_change_ids", {u.id: u for u in unit_changes}),
        ("risk_ids", {r.id: r for r in risks}),
    )
    out: list[ConclusionItem] = []
    for n, item in enumerate(items, start=1):
        entities = []
        unknown = []
        for field, by_id in groups:
            ids = getattr(item, field)
            entities.extend(by_id[id_] for id_ in ids if id_ in by_id)
            unknown.extend(id_ for id_ in ids if id_ not in by_id)
        if unknown or not entities or not item.text.strip():
            warnings.append(f"Conclusion item {n} dropped: missing or unknown evidence IDs: {unknown}.")
            continue
        evidence = [c for entity in entities for c in entity.citations]
        citations = item.citations or evidence
        problem = next(
            (
                check_citation(c, index) or "citation does not belong to the referenced outputs"
                for c in citations
                if check_citation(c, index) is not None or not any(
                    _key(c) == _key(source) and c.quote in source.quote for source in evidence
                )
            ),
            None,
        )
        if problem or not citations:
            warnings.append(f"Conclusion item {n} dropped: {problem or 'no verified citation'}.")
            continue
        out.append(item.model_copy(update={"citations": citations}))
    return out


def _domain_conclusion(unit_changes: list[UnitChange], risks: list[Risk]) -> list[ConclusionItem]:
    items: list[ConclusionItem] = []
    unit_labels = {
        "retained": "Сохранившиеся подразделения",
        "reorganised": "Преобразованные подразделения",
        "created": "Созданные подразделения без подтверждённого предшественника",
        "unresolved": "Подразделения с неподтверждённой преемственностью",
    }
    for status, label in unit_labels.items():
        rows = [u for u in unit_changes if u.status == status]
        if rows:
            items.append(ConclusionItem(
                text=f"{label}: {len(rows)}. Проверьте источники и границы переданных полномочий.",
                unit_change_ids=[u.id for u in rows],
                citations=list({(_key(c), c.quote): c for u in rows for c in u.citations}.values()),
            ))
    for kind, label in (
        ("potential_duplication", "Возможное межподразделенческое дублирование"),
        ("potential_conflict_of_interest", "Потенциальный конфликт исполнения и проверки собственной работы"),
    ):
        rows = [r for r in risks if r.kind == kind]
        if rows:
            items.append(ConclusionItem(
                text=f"{label}: {len(rows)}. Вывод рекомендательный, не свидетельство нарушения; "
                     "ответственному сотруднику следует проверить распределение обязанностей по указанным источникам.",
                risk_ids=[r.id for r in rows],
                citations=list({(_key(c), c.quote): c for r in rows for c in r.citations}.values()),
            ))
    return items


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
    unit_changes: list[UnitChange] | None = None,
    risks: list[Risk] | None = None,
    agent: AgentExecution | None = None,
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
    if unit_changes is None or risks is None:
        generated_units, generated_risks, domain_notes = analyze_domain(documents, clauses, units, checked)
        notes.extend(domain_notes)
    else:
        generated_units, generated_risks = [], []
    checked_units: list[UnitChange] = []
    checked_risks: list[Risk] = []
    seen_units: set[str] = set()
    seen_risks: set[str] = set()
    for change in generated_units if unit_changes is None else unit_changes:
        problem = validate_unit_change(change, documents, clauses, units, reviewed_predecessors=True)
        if change.id in seen_units:
            problem = "duplicate unit change ID"
        if problem:
            notes.append(f"{change.id}: unit change withheld — {problem}.")
        else:
            seen_units.add(change.id)
            checked_units.append(change)
    risk_evidence: set[tuple] = set()
    for risk in generated_risks if risks is None else risks:
        problem = validate_risk(risk, documents, clauses, units)
        if risk.id in seen_risks:
            problem = "duplicate risk ID"
        signature = (risk.kind, tuple(sorted({_key(r) for r in risk.refs})))
        if problem:
            notes.append(f"{risk.id}: risk withheld — {problem}.")
        elif signature not in risk_evidence:
            seen_risks.add(risk.id)
            risk_evidence.add(signature)
            checked_risks.append(risk)
    coverage = compute_coverage(clauses, checked, before_docs, after_docs)
    items: list[ConclusionItem] | None = None
    if conclusion is not None:
        items = _validate_conclusion(conclusion, checked, index, notes, checked_units, checked_risks)
        if not items:
            notes.append("Proposed conclusion rejected: no item referenced verified findings; deterministic conclusion used.")
            items = None
    if items is None:
        items = deterministic_conclusion(checked, coverage, documents)
    # Mandatory domain sections are never lost to an abbreviated model conclusion.
    linked_units = {id_ for item in items for id_ in item.unit_change_ids}
    linked_risks = {id_ for item in items for id_ in item.risk_ids}
    items.extend(_domain_conclusion(
        [u for u in checked_units if u.id not in linked_units],
        [r for r in checked_risks if r.id not in linked_risks],
    ))
    execution = agent or AgentExecution(status="not_requested", stop_reason="Model investigation not requested.")
    if execution.status != "not_requested":
        notes.append(
            f"Агент: {execution.status}; исследовано выводов {len(execution.investigated_finding_ids)} "
            f"из {len(checked)}; {execution.stop_reason}"
        )
    notes.append("Выводы рекомендательные и требуют проверки ответственным сотрудником. "
                 "Отсутствие отмеченного риска не доказывает отсутствие пересечения или конфликта.")
    return Report(
        run_id=run_id,
        mode=mode,
        documents=documents,
        clauses=clauses,
        units=units,
        findings=checked,
        conclusion=items,
        coverage=coverage,
        warnings=list(dict.fromkeys(notes)),
        unit_changes=checked_units,
        risks=checked_risks,
        agent=execution,
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
    elif len({_key(r) for r in before}) != len(before) or len({_key(r) for r in after}) != len(after):
        problem = "repeated clause references cannot satisfy alignment cardinality"
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
        reason=f"Предложение модели: статус «{status}» для указанных пунктов до и после. "
               "Сопоставление основано на приведённых источниках и требует проверки ответственным сотрудником.",
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
