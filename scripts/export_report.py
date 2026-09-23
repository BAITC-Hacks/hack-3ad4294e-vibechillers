#!/usr/bin/env python3
"""Export a public Function Lineage Auditor Report JSON to offline HTML."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any


LABELS = {
    "before": "До", "after": "После",
    "deterministic": "Детерминированный", "llm_assisted": "С участием модели",
    "unchanged": "Без изменений", "changed": "Изменена", "moved": "Перенесена",
    "added": "Добавлена", "missing": "Возможная потеря", "duplicate": "Возможное дублирование",
    "unresolved": "Не установлено", "retained": "Сохранено",
    "reorganised": "Реорганизовано", "created": "Создано",
    "potential_duplication": "Потенциальное межподразделенческое дублирование",
    "potential_conflict_of_interest": "Потенциальный конфликт интересов",
    "exact": "Точное сопоставление", "lexical": "Лексическое сопоставление",
    "llm": "Модель", "human": "Эксперт",
    "not_requested": "Не запрашивался", "completed": "Завершён",
    "partial": "Частично выполнен", "unavailable": "Недоступен", "failed": "Ошибка",
    "unit": "Подразделение", "role": "Роль", "heading": "Заголовок",
    "function": "Функция", "structure": "Структура", "other": "Прочее",
}


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def label(value: Any) -> str:
    return esc(LABELS.get(str(value), str(value) if value is not None else "Не указано"))


def anchor(kind: str, *parts: str) -> str:
    key = json.dumps(parts, ensure_ascii=False).encode("utf-8")
    return kind + "-" + hashlib.sha256(key).hexdigest()


def source_location(location: dict[str, Any] | None) -> str:
    if not location:
        return "Координаты источника не указаны"
    fields = (("page", "Страница"), ("block", "Блок"),
              ("sheet", "Лист"), ("cell_range", "Ячейки"))
    return "; ".join(f"{name}: {esc(location[key])}" for key, name in fields
                     if location.get(key) is not None) or "Координаты источника не указаны"


def render_report(report: dict[str, Any]) -> str:
    documents = report.get("documents") or []
    clauses = report.get("clauses") or []
    units = report.get("units") or []
    findings = report.get("findings") or []
    changes = report.get("unit_changes")
    risks = report.get("risks")
    clause_index = {(str(c.get("doc", "")), str(c.get("clause_id", ""))): c for c in clauses}
    unit_index = {(str(u.get("doc", "")), str(u.get("unit_id", ""))): u for u in units}
    document_index = {str(d.get("doc", "")): d for d in documents}
    # Ambiguous IDs cannot be navigated safely: dictionaries and HTML fragment
    # resolution otherwise disagree about which duplicate is the source.
    for items, keys in (
        (documents, ("doc",)), (clauses, ("doc", "clause_id")),
        (units, ("doc", "unit_id")), (findings, ("id",)),
        (changes or [], ("id",)), (risks or [], ("id",)),
    ):
        seen = set()
        for item in items:
            identity = tuple(str(item.get(key, "")) for key in keys)
            if identity in seen:
                raise ValueError(f"Неоднозначный идентификатор источника/результата: {identity!r}")
            seen.add(identity)
    result_ids = {
        "finding": {str(f.get("id", "")) for f in findings},
        "unit-change": {str(c.get("id", "")) for c in changes or []},
        "risk": {str(r.get("id", "")) for r in risks or []},
    }

    def link(target: str, text: str, exists: bool) -> str:
        if exists:
            return f'<a href="#{target}">{text}</a>'
        return f'<span class="unavailable">{text} (источник или результат отсутствует в отчёте)</span>'

    def clause_link(doc: str, clause_id: str) -> str:
        return link(anchor("clause", doc, clause_id), f"{esc(doc)} §{esc(clause_id)}",
                    (doc, clause_id) in clause_index)

    def unit_link(doc: str, unit_id: str) -> str:
        unit = unit_index.get((doc, unit_id))
        name = f" — {esc(unit.get('name', ''))}" if unit else ""
        return link(anchor("unit", doc, unit_id), f"{esc(doc)} / {esc(unit_id)}{name}", unit is not None)

    def result_links(kind: str, ids: list[str]) -> str:
        return " · ".join(link(anchor(kind, str(i)), esc(i), str(i) in result_ids[kind]) for i in ids)

    def citations_html(item: dict[str, Any]) -> str:
        rendered = []
        for citation in item.get("citations", []):
            doc, clause_id = str(citation.get("doc", "")), str(citation.get("clause_id", ""))
            quote = str(citation.get("quote", ""))
            clause = clause_index.get((doc, clause_id))
            # Only exact, nonempty quotes in the referenced clause are navigable citations.
            exact = clause is not None and bool(quote) and quote in str(clause.get("text", ""))
            text = f"{esc(doc)} §{esc(clause_id)}: &laquo;{esc(quote)}&raquo;"
            if exact:
                rendered.append(link(anchor("clause", doc, clause_id), text, True))
            else:
                problem = "Исходный пункт отсутствует" if clause is None else "Точная цитата не подтверждена"
                rendered.append(f'<span class="unavailable">{text} — {problem}</span>')
        return f'<div class="citations">{"<br>".join(rendered)}</div>' if rendered else "<p class=meta>Цитаты не представлены.</p>"

    def reference_html(ref: dict[str, Any], expected: str, structural: bool = False,
                       unit: bool = False) -> str:
        doc = str(ref.get("doc", ""))
        result = unit_link(doc, str(ref.get("unit_id", ""))) if unit else clause_link(
            doc, str(ref.get("clause_id", "")))
        if document_index.get(doc, {}).get("edition") != expected:
            result += f'<span class="unavailable"> — ссылка не соответствует редакции «{label(expected)}»</span>'
        source_unit = unit_index.get((doc, str(ref.get("unit_id", ""))))
        if structural and source_unit and source_unit.get("kind") != "unit":
            result += '<span class="unavailable"> — указана роль, а не структурное подразделение</span>'
        return result

    def refs_html(item: dict[str, Any], unit_refs: bool = False) -> str:
        fields = ("before", "after") if "refs" not in item else ("refs",)
        rows = []
        for field in fields:
            refs = item.get(field, [])
            links = " · ".join(reference_html(r, "after" if field == "refs" else field,
                                              structural=unit_refs, unit=unit_refs) for r in refs)
            rows.append(f"<dt>{'Пункты' if field == 'refs' else label(field)}</dt><dd>{links or 'Не указаны'}</dd>")
        return f'<dl>{"".join(rows)}</dl>'

    def decision_html(item: dict[str, Any], kind: str) -> str:
        item_id = str(item.get("id", ""))
        review = {True: "Да", False: "Нет"}.get(item.get("review_required"), "Не указано")
        refs = refs_html(item, kind == "unit-change")
        if kind == "risk":
            refs += '<p>Подразделения / роли: ' + (" · ".join(
                reference_html(r, "after", unit=True)
                for r in item.get("units", [])
            ) or "Не указаны") + "</p>"
        return (
            f'<article id="{anchor(kind, item_id)}"><h3><span class="status">'
            f'{label(item.get("kind") if kind == "risk" else item.get("status"))}</span> {esc(item_id)}</h3>'
            f'<p>{esc(item.get("reason", ""))}</p><p class="meta">Метод: {label(item.get("method"))}; '
            f'Требуется проверка: {review}</p>{refs}{citations_html(item)}</article>'
        )

    document_items = []
    for document in documents:
        # Sources are identifiers, not requests: the offline report never loads external resources.
        source = document.get("source") or "Не указан"
        document_items.append(
            f'<li><strong>{esc(document.get("doc", ""))}</strong> ({label(document.get("edition"))}) '
            f'— {esc(source)}<p class="meta">ID документа: {esc(document.get("doc_id", "Не указан"))}; '
            f'SHA-256: {esc(document.get("sha256", "Не указан"))}</p></li>'
        )

    conclusion_items = []
    for item in report.get("conclusion") or []:
        links = []
        for field, kind, heading in (("finding_ids", "finding", "Сопоставления функций"),
                                     ("unit_change_ids", "unit-change", "Изменения подразделений"),
                                     ("risk_ids", "risk", "Межподразделенческие риски")):
            ids = item.get(field, [])
            if ids:
                links.append(f'<p class="meta">{heading}: {result_links(kind, ids)}</p>')
        conclusion_items.append(f'<li><p>{esc(item.get("text", ""))}</p>{"".join(links)}{citations_html(item)}</li>')

    unit_items = []
    for unit in units:
        doc, unit_id = str(unit.get("doc", "")), str(unit.get("unit_id", ""))
        parent = unit.get("parent_unit_id")
        parent_html = unit_link(doc, str(parent)) if parent is not None else "Не указан"
        unit_items.append(
            f'<article id="{anchor("unit", doc, unit_id)}"><h3>{esc(unit.get("name", ""))}</h3>'
            f'<p class="meta">Документ: {esc(doc)}; ID: {esc(unit_id)}; тип: {label(unit.get("kind"))}; '
            f'Родительское подразделение / роль: {parent_html}</p>{citations_html(unit)}</article>'
        )

    clause_items = []
    for clause in clauses:
        doc, clause_id = str(clause.get("doc", "")), str(clause.get("clause_id", ""))
        parent = clause.get("parent_id")
        parent_html = clause_link(doc, str(parent)) if parent is not None else "Не указан"
        owners = " · ".join(unit_link(doc, str(u)) for u in clause.get("unit_ids", [])) or "Не указаны"
        clause_items.append(
            f'<article id="{anchor("clause", doc, clause_id)}"><h3>{esc(doc)} §{esc(clause_id)} '
            f'<span class="kind">{label(clause.get("kind"))}</span></h3>'
            f'<p class="label">{esc(clause.get("label", ""))}</p>'
            f'<p class="source-text">{esc(clause.get("text", ""))}</p>'
            f'<p class="meta">{source_location(clause.get("location"))}; '
            f'Порядковый номер: {esc(clause.get("ordinal", "Не указан"))}</p>'
            f'<p>Родительский пункт: {parent_html}</p><p>Подразделения / роли из источника: {owners}</p></article>'
        )

    agent = report.get("agent")
    if agent is None:
        agent_html = "<p>Не оценивалось: сведения о выполнении агента отсутствуют в сохранённом отчёте.</p>"
    else:
        investigated = agent.get("investigated_finding_ids", [])
        agent_html = (
            f'<p>Статус: <strong>{label(agent.get("status"))}</strong>; '
            f'Модель: {esc(agent.get("model") or "Не указана")}; '
            f'Ходы: {esc(agent.get("turns", "Не указано"))}; '
            f'Вызовы инструментов: {esc(agent.get("tool_calls", "Не указано"))}</p>'
            f'<p>Причина остановки: {esc(agent.get("stop_reason", "Не указана"))}</p>'
            f'<p>Исследованные сопоставления: {result_links("finding", investigated) or "Не указаны"}</p>'
            '<p class="meta">Статус агента не означает проверку всего отчёта. '
            'Список выше отражает только явно указанные исследованные сопоставления; '
            'отчёт не содержит журнала вызовов инструментов.</p>'
        )

    coverage = report.get("coverage") or {}
    coverage_text = "; ".join(
        f"{name}: {esc(coverage[key])}" for key, name in (
            ("before_total", "Функций до"), ("after_total", "Функций после"),
            ("before_accounted", "Учтено до"), ("after_accounted", "Учтено после"),
            ("unresolved", "Не разрешено"),
        ) if key in coverage
    ) or "Покрытие не указано"
    warnings = "".join(f"<li>{esc(w)}</li>" for w in report.get("warnings") or [])
    changes_html = ("<p>Не оценивалось: поле unit_changes отсутствует или выполнение Stage 3 не подтверждено.</p>" if changes is None or (not changes and agent is None) else
                    "".join(decision_html(c, "unit-change") for c in changes) or
                    "<p>Список изменений подразделений пуст. Это не подтверждает сохранение всех подразделений.</p>")
    risks_html = ("<p>Не оценивалось: поле risks отсутствует или выполнение Stage 3 не подтверждено.</p>" if risks is None or (not risks and agent is None) else
                  "".join(decision_html(r, "risk") for r in risks) or
                  "<p>Список межподразделенческих рисков пуст. Это не доказывает отсутствие дублирования или конфликтов.</p>")
    return f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Аудит функций — {esc(report.get("run_id", ""))}</title>
<style>body {{ font: 16px/1.5 system-ui,sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 1rem; color: #202124; overflow-wrap: anywhere }}
a {{ color: #075985 }} .meta,.label,.kind {{ color: #5f6368; font-size: .9rem }}
.warnings,.advisory {{ border: 2px solid #b45309; background: #fff7ed; padding: .75rem 1rem; margin: 1rem 0 }}
article {{ border: 1px solid #d1d5db; padding: .8rem 1rem; margin: .75rem 0; scroll-margin-top: 1rem }}
article:target {{ outline: 3px solid #f59e0b }} .status {{ background: #e0f2fe; padding: .15rem .4rem }}
.unavailable {{ color: #92400e }} .source-text {{ white-space: pre-wrap }}
dt {{ font-weight: 700 }} dd {{ margin: 0 0 .35rem }} .citations {{ overflow-wrap: anywhere }}</style></head><body>
<h1>Аудит функций и подразделений</h1>
<p class="meta">Запуск: {esc(report.get("run_id", ""))}; режим: {label(report.get("mode"))}</p>
<aside class="advisory"><strong>Рекомендательный отчёт.</strong> Выводы требуют проверки ответственным экспертом.
Потенциальный конфликт интересов — основание для проверки, а не доказательство нарушения или неправомерных действий.
Покрытие и точность цитат не подтверждают смысловую правильность выводов.</aside>
<section><h2>Документы</h2><ul>{''.join(document_items) or '<li>Документы не представлены.</li>'}</ul></section>
<section><h2>Покрытие</h2><p>{coverage_text}</p></section>
<section><h2>Выполнение агента</h2>{agent_html}</section>
<section class="warnings"><h2>Предупреждения и ограничения</h2><ul>{warnings or '<li>Предупреждения не представлены; это не подтверждает полноту проверки.</li>'}</ul></section>
<section><h2>Аналитическое заключение</h2><ol>{''.join(conclusion_items) or '<li>Заключение не представлено.</li>'}</ol></section>
<section><h2>Изменения подразделений</h2>{changes_html}</section>
<section><h2>Сопоставления функций</h2>{''.join(decision_html(f, 'finding') for f in findings) or '<p>Сопоставления не представлены.</p>'}</section>
<section><h2>Межподразделенческие риски</h2>{risks_html}</section>
<section><h2>Подразделения и роли</h2>{''.join(unit_items) or '<p>Подразделения и роли не представлены.</p>'}</section>
<section><h2>Исходные пункты и контекст</h2><p class="meta">Родительские связи и роли показаны только из полей отчёта; экспорт не выводит обязанности из заголовков.</p>{''.join(clause_items) or '<p>Исходные пункты не представлены.</p>'}</section>
</body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8-sig"))
    if not isinstance(report, dict):
        raise SystemExit("Report JSON must be an object")
    try:
        rendered = render_report(report)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered, encoding="utf-8")
    print(f"HTML report saved to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
