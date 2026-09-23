"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { BookOpenText, ChevronLeft, ChevronRight, Eye, FileText, Search, TriangleAlert, X } from "lucide-react";
import type { AgentExecution, Citation, ClauseRef, Finding, FindingMethod, FindingStatus, Report, Risk, UnitChange, UnitRef } from "../lib/api";
import { STATUS_LABEL, STATUS_MEANING, STATUS_ORDER, STATUS_STYLE, buildReportIndex, checkCitation, clauseAncestors, clauseUnits, refKey, sourceLocation, unitChain, type ReportIndex } from "../lib/audit";

interface ClauseSelection extends ClauseRef { quote: string | null }
type OpenClause = (selection: ClauseSelection) => void;
type Section = "findings" | "units" | "risks";
const PAGE_SIZE = 25;
const button = "rounded border border-neutral-700 px-2 py-1 text-xs text-neutral-200 hover:border-amber-600 focus-visible:outline-amber-400 disabled:opacity-40";
const panel = "rounded-lg border border-neutral-800 bg-neutral-900/40 p-3";
const unitLabels: Record<UnitChange["status"], string> = { retained: "Сохранено", created: "Создано", reorganised: "Реорганизовано", unresolved: "Не определено" };
const riskLabels: Record<Risk["kind"], string> = { potential_duplication: "Возможное межподразделенческое дублирование", potential_conflict_of_interest: "Потенциальный конфликт интересов" };
const methodLabels: Record<FindingMethod, string> = { exact: "Точное сопоставление", lexical: "Лексическое сопоставление", llm: "Модель", human: "Эксперт" };
const agentLabels: Record<AgentExecution["status"], string> = { not_requested: "Не запрашивался", completed: "Завершён в указанном объёме", partial: "Частично выполнен", unavailable: "Недоступен", failed: "Ошибка" };
const kindLabels = { heading: "Заголовок", function: "Функция", structure: "Структура", other: "Другой текст", unit: "Подразделение", role: "Роль" };

function StatusBadge({ status }: { status: FindingStatus }) {
  return <span title={STATUS_MEANING[status]} className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] ${STATUS_STYLE[status]}`}>{STATUS_LABEL[status]}</span>;
}

function ReviewLabel({ required }: { required: boolean }) {
  return <span className={`inline-flex items-center gap-1 text-[11px] ${required ? "text-amber-300" : "text-neutral-400"}`}><Eye size={12} />{required ? "Требуется проверка" : "Обязательная проверка не отмечена"}</span>;
}

function CitationLink({ citation, index, onOpen }: { citation: Citation; index: ReportIndex; onOpen: OpenClause }) {
  const check = checkCitation(index, citation);
  return <button type="button" onClick={() => onOpen(citation)} title={check.ok ? `${sourceLocation(check.clause)}\n${citation.quote}` : `Цитата не подтверждена: ${check.reason}`} className={`inline-flex max-w-full items-start gap-1 rounded border px-2 py-1 text-left text-[11px] ${check.ok ? "border-neutral-700 text-neutral-300 hover:border-amber-600" : "border-red-800 text-red-200"}`}>
    {check.ok ? <BookOpenText size={12} className="mt-0.5 shrink-0 text-amber-400" /> : <TriangleAlert size={12} className="mt-0.5 shrink-0" />}
    <span className="min-w-0 break-words"><span className="font-mono">{citation.doc} §{citation.clause_id}</span> · «{citation.quote.length > 100 ? `${citation.quote.slice(0, 100)}…` : citation.quote}»{!check.ok && <span className="block">{check.reason}</span>}</span>
  </button>;
}

function Evidence({ citations, index, onOpen }: { citations: Citation[]; index: ReportIndex; onOpen: OpenClause }) {
  return <div className="space-y-1"><h4 className="text-[11px] text-neutral-500">Дословные основания</h4>{citations.length ? <div className="flex flex-wrap gap-1">{citations.map((citation, i) => <CitationLink key={i} citation={citation} index={index} onOpen={onOpen} />)}</div> : <p className="text-xs text-amber-300">Цитаты не предоставлены; основание этого вывода не подтверждено в отчёте.</p>}</div>;
}

function ClauseReferences({ refs, citations, index, onOpen, expected }: { refs: ClauseRef[]; citations: Citation[]; index: ReportIndex; onOpen: OpenClause; expected?: "before" | "after" }) {
  if (!refs.length) return <p className="text-xs text-neutral-500">Подтверждённая ссылка не указана.</p>;
  return <ul className="space-y-2">{refs.map((ref, i) => {
    const clause = index.clauses.get(refKey(ref.doc, ref.clause_id));
    const quote = citations.find((c) => c.doc === ref.doc && c.clause_id === ref.clause_id)?.quote ?? null;
    const wrongEdition = expected && index.docs.get(ref.doc)?.edition !== expected;
    return <li key={`${refKey(ref.doc, ref.clause_id)}-${i}`}>
      <button type="button" className="w-full rounded border border-neutral-800 px-2 py-1.5 text-left hover:border-amber-700" onClick={() => onOpen({ ...ref, quote })}>
        <span className="font-mono text-xs text-amber-200">{ref.doc} §{ref.clause_id}</span>
        {clause ? <><span className="mt-1 block line-clamp-3 whitespace-pre-wrap break-words text-xs text-neutral-300">{clause.text}</span><span className="mt-1 block text-[10px] text-neutral-500">{sourceLocation(clause)}</span></> : <span className="block text-xs text-red-300">Пункт отсутствует в отчёте</span>}
        {wrongEdition && <span className="block text-xs text-red-300">Ссылка не соответствует редакции «{expected === "before" ? "до" : "после"}».</span>}
      </button>
    </li>;
  })}</ul>;
}

function UnitReferences({ refs, index, onOpen, expected, structural = false }: { refs: UnitRef[]; index: ReportIndex; onOpen: OpenClause; expected: "before" | "after"; structural?: boolean }) {
  if (!refs.length) return <p className="text-xs text-neutral-500">Подтверждённое подразделение не указано.</p>;
  return <ul className="space-y-2">{refs.map((ref, i) => {
    const unit = index.units.get(refKey(ref.doc, ref.unit_id));
    return <li key={`${refKey(ref.doc, ref.unit_id)}-${i}`} className="space-y-1 rounded border border-neutral-800 p-2">
      <div className="break-words text-xs text-neutral-200">{unit ? unitChain(index, unit).map((u) => u.name).join(" › ") : "Подразделение не найдено"}</div>
      <div className="break-all font-mono text-[10px] text-neutral-500">{ref.doc} · {ref.unit_id}{unit && ` · ${kindLabels[unit.kind]}`}</div>
      {index.docs.get(ref.doc)?.edition !== expected && <p className="text-xs text-red-300">Ссылка не соответствует редакции «{expected === "before" ? "до" : "после"}».</p>}
      {unit && structural && unit.kind !== "unit" && <p className="text-xs text-red-300">Указана роль, а не структурное подразделение.</p>}
      {unit ? <>{unitChain(index, unit).map((part) => <div key={part.unit_id} className="space-y-1">{part !== unit && <p className="text-[10px] text-neutral-500">Вышестоящий контекст: {part.name}</p>}{part.citations.map((citation, j) => <CitationLink key={j} citation={citation} index={index} onOpen={onOpen} />)}</div>)}{!unit.citations.length && <p className="text-xs text-amber-300">Определяющий источник не указан.</p>}</> : <p className="text-xs text-red-300">Ссылка не разрешается в этом отчёте.</p>}
    </li>;
  })}</ul>;
}

function ClauseViewer({ selection, index, onOpen, onClose }: { selection: ClauseSelection | null; index: ReportIndex; onOpen: OpenClause; onClose: () => void }) {
  const markRef = useRef<HTMLElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (selection) titleRef.current?.focus({ preventScroll: true });
    markRef.current?.scrollIntoView({ block: "nearest" });
  }, [selection]);
  if (!selection) return <div className="p-6 text-center text-xs text-neutral-500">Выберите ссылку на пункт или цитату. Здесь откроются точный текст, координаты и контекст ответственного.</div>;
  const clause = index.clauses.get(refKey(selection.doc, selection.clause_id));
  const doc = index.docs.get(selection.doc);
  const check = selection.quote === null ? null : checkCitation(index, { ...selection, quote: selection.quote });
  const siblings = index.byDoc.get(selection.doc) ?? [];
  const position = clause ? siblings.indexOf(clause) : -1;
  const prev = position > 0 ? siblings[position - 1] : undefined;
  const next = position >= 0 ? siblings[position + 1] : undefined;
  const ancestors = clause ? clauseAncestors(index, clause) : [];
  const units = clause ? clauseUnits(index, clause) : [];
  return <div className="flex min-h-0 flex-col" onKeyDown={(event) => { if (event.key === "Escape") onClose(); }}>
    <header className="flex items-start gap-2 border-b border-neutral-800 p-3">
      <FileText size={16} className="mt-0.5 shrink-0 text-amber-400" />
      <div className="min-w-0 flex-1"><h3 ref={titleRef} tabIndex={-1} className="break-words text-sm font-medium text-neutral-100 outline-none">Источник: {selection.doc} §{selection.clause_id}</h3>{doc && <p className="mt-1 break-words text-[11px] text-neutral-400" title={`SHA-256: ${doc.sha256}`}>{doc.edition === "before" ? "До" : "После"} · {doc.source}</p>}</div>
      <button type="button" onClick={onClose} aria-label="Закрыть источник" className="rounded p-1 text-neutral-400 hover:bg-neutral-800"><X size={16} /></button>
    </header>
    <div className="min-h-0 space-y-3 overflow-y-auto p-3 text-xs">
      {!clause ? <p className="text-red-300">Пункт отсутствует в сохранённом отчёте. Ссылка не может быть проверена.</p> : <>
        {!!ancestors.length && <nav aria-label="Родительские пункты" className="flex flex-wrap items-center gap-1 text-neutral-400">{ancestors.map((parent) => <span key={parent.clause_id} className="flex items-center gap-1"><button type="button" title={parent.text} onClick={() => onOpen({ doc: parent.doc, clause_id: parent.clause_id, quote: null })} className="hover:text-amber-200">§{parent.clause_id}</button><ChevronRight size={12} /></span>)}</nav>}
        <div className="space-y-1 text-neutral-400"><p>{kindLabels[clause.kind]}{clause.label && ` · Метка «${clause.label}»`}</p><p className="text-amber-200">{sourceLocation(clause)}</p><p className="text-[10px]">Порядок извлечённого блока: {clause.ordinal} (не номер страницы).</p></div>
        {check && !check.ok && <div role="alert" className="rounded border border-red-800 p-2 text-red-200"><p>Цитата не подтверждена: {check.reason}</p><p className="mt-1 whitespace-pre-wrap break-words">Заявленная цитата: «{selection.quote}»</p></div>}
        <div className="whitespace-pre-wrap break-words rounded border border-neutral-700 bg-neutral-950/60 p-3 text-[13px] leading-relaxed text-neutral-200">{check?.ok ? <>{clause.text.slice(0, check.start)}<mark ref={markRef} className="rounded bg-amber-400/25 text-amber-100 ring-1 ring-amber-500/60">{clause.text.slice(check.start, check.end)}</mark>{clause.text.slice(check.end)}</> : clause.text}</div>
        {!!ancestors.length && <section aria-label="Определяющий контекст" className="space-y-2"><h4 className="font-medium text-neutral-300">Определяющий контекст и ответственный</h4><p className="text-neutral-400">Родительский пункт может определять обязанность, полномочие или ограничение. Это отдельный источник, а не часть выбранного пункта.</p>{[...ancestors].reverse().map((parent) => <div key={parent.clause_id} className="space-y-1 rounded border border-neutral-800 p-2"><CitationLink citation={{ doc: parent.doc, clause_id: parent.clause_id, quote: parent.text }} index={index} onOpen={onOpen} /><p className="whitespace-pre-wrap break-words text-neutral-300">{parent.text}</p></div>)}</section>}
        <section className="space-y-2"><h4 className="font-medium text-neutral-300">Подразделения и роли в контексте</h4><p className="text-neutral-400">Упоминание получателя или делегата само по себе не устанавливает ответственность. Сверьте определяющие и родительские источники.</p>{units.length ? units.map((unit) => <div key={unit.unit_id} className="space-y-2 rounded border border-neutral-800 p-2">{unitChain(index, unit).map((part) => <div key={part.unit_id} className="space-y-1"><p className="break-words text-neutral-200">{part.name} <span className="text-neutral-500">· {kindLabels[part.kind]} · {part.unit_id}</span></p>{part.citations.length ? part.citations.map((citation, i) => <CitationLink key={i} citation={citation} index={index} onOpen={onOpen} />) : <p className="text-amber-300">Определяющая цитата не указана.</p>}</div>)}</div>) : <p className="text-neutral-500">Связанные подразделения и роли не указаны.</p>}</section>
        <nav className="flex justify-between gap-2" aria-label="Соседние пункты"><button type="button" className={button} disabled={!prev} onClick={() => prev && onOpen({ doc: prev.doc, clause_id: prev.clause_id, quote: null })}><ChevronLeft size={12} className="inline" /> {prev ? `§${prev.clause_id}` : "Начало"}</button><button type="button" className={button} disabled={!next} onClick={() => next && onOpen({ doc: next.doc, clause_id: next.clause_id, quote: null })}>{next ? `§${next.clause_id}` : "Конец"} <ChevronRight size={12} className="inline" /></button></nav>
      </>}
    </div>
  </div>;
}

function Pagination({ page, total, onChange }: { page: number; total: number; onChange: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  return <nav aria-label="Страницы результатов" className="flex flex-wrap items-center justify-between gap-2 border-t border-neutral-800 p-3 text-xs text-neutral-400"><span>{total ? `${page * PAGE_SIZE + 1}–${Math.min(total, (page + 1) * PAGE_SIZE)} из ${total}` : "0 результатов"} · страница {page + 1}/{pages}</span><div className="flex gap-2"><button type="button" className={button} disabled={page === 0} onClick={() => onChange(page - 1)}>Назад</button><button type="button" className={button} disabled={page + 1 >= pages} onClick={() => onChange(page + 1)}>Далее</button></div></nav>;
}

function FindingDetail({ finding, index, onOpen }: { finding: Finding; index: ReportIndex; onOpen: OpenClause }) {
  const direct = new Set([...finding.before, ...finding.after].map((ref) => refKey(ref.doc, ref.clause_id)));
  const context = finding.citations.filter((citation) => !direct.has(refKey(citation.doc, citation.clause_id)));
  return <div className="space-y-3"><p className="whitespace-pre-wrap break-words text-xs text-neutral-200">{finding.reason}</p><p className="text-xs text-neutral-400">{STATUS_MEANING[finding.status]}</p><div className="grid gap-3 md:grid-cols-2"><section className="space-y-1"><h4 className="text-xs font-medium text-sky-300">До</h4><ClauseReferences refs={finding.before} citations={finding.citations} index={index} onOpen={onOpen} expected="before" /></section><section className="space-y-1"><h4 className="text-xs font-medium text-emerald-300">После</h4><ClauseReferences refs={finding.after} citations={finding.citations} index={index} onOpen={onOpen} expected="after" /></section></div><Evidence citations={finding.citations.filter((citation) => direct.has(refKey(citation.doc, citation.clause_id)))} index={index} onOpen={onOpen} />{!!context.length && <section className="space-y-1"><h4 className="text-xs text-neutral-400">Дополнительные источники контекста</h4>{context.map((citation, i) => <CitationLink key={i} citation={citation} index={index} onOpen={onOpen} />)}</section>}</div>;
}

/** Source-backed review only: domain decisions remain exactly those in Report. */
export function AuditReportView(props: { report: Report; llmRequested: boolean | null }) {
  return <ReportReviewer key={props.report.run_id} {...props} />;
}

function ReportReviewer({ report, llmRequested }: { report: Report; llmRequested: boolean | null }) {
  const index = useMemo(() => buildReportIndex(report), [report]);
  const [selection, setSelection] = useState<ClauseSelection | null>(null);
  const [section, setSection] = useState<Section>("findings");
  const [filter, setFilter] = useState("all");
  const [reviewOnly, setReviewOnly] = useState(false);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [focus, setFocus] = useState<{ section: Section; id: string; serial: number } | null>(null);
  const [navigationError, setNavigationError] = useState<string | null>(null);
  const reportStart = useRef<HTMLElement>(null);
  useEffect(() => {
    if (focus) document.getElementById(`audit-${focus.section}-${focus.id}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [focus]);

  const related = useMemo(() => {
    const byClause = new Map<string, Set<string>>();
    for (const risk of report.risks ?? []) {
      if (risk.kind !== "potential_duplication") continue;
      for (const ref of risk.refs) {
        const key = refKey(ref.doc, ref.clause_id);
        if (!byClause.has(key)) byClause.set(key, new Set());
        byClause.get(key)!.add(risk.id);
      }
    }
    const byFinding = new Map<string, string[]>();
    for (const finding of report.findings) {
      if (finding.status !== "duplicate") continue;
      const ids = new Set<string>();
      for (const ref of finding.after) for (const id of byClause.get(refKey(ref.doc, ref.clause_id)) ?? []) ids.add(id);
      if (ids.size) byFinding.set(finding.id, [...ids]);
    }
    const byRisk = new Map<string, string[]>();
    for (const [id, risks] of byFinding) for (const risk of risks) {
      const ids = byRisk.get(risk);
      if (ids) ids.push(id); else byRisk.set(risk, [id]);
    }
    return { byFinding, byRisk };
  }, [report.findings, report.risks]);
  const investigated = useMemo(() => new Set(report.agent?.investigated_finding_ids ?? []), [report.agent]);
  const investigatedKnown = report.findings.filter((finding) => investigated.has(finding.id)).length;
  const counts = useMemo(() => {
    const result: Record<string, number> = {};
    const rows = section === "findings" ? report.findings : section === "units" ? report.unit_changes ?? [] : report.risks ?? [];
    for (const row of rows) { const key = "kind" in row ? row.kind : row.status; result[key] = (result[key] ?? 0) + 1; }
    return result;
  }, [report, section]);
  const searchable = useMemo(() => {
    const clauseText = (ref: ClauseRef) => { const clause = index.clauses.get(refKey(ref.doc, ref.clause_id)); return `${ref.doc} ${ref.clause_id} ${clause?.text ?? ""} ${clause ? sourceLocation(clause) : ""}`; };
    const unitText = (ref: UnitRef) => `${ref.doc} ${ref.unit_id} ${index.units.get(refKey(ref.doc, ref.unit_id))?.name ?? ""}`;
    const rows: { id: string; status: string; review: boolean; text: string }[] = section === "findings" ? report.findings.map((row) => ({ id: row.id, status: row.status, review: row.review_required, text: `${row.id} ${row.reason} ${[...row.before, ...row.after].map(clauseText).join(" ")} ${row.citations.map((c) => c.quote).join(" ")}` })) : section === "units" ? (report.unit_changes ?? []).map((row) => ({ id: row.id, status: row.status, review: row.review_required, text: `${row.id} ${row.reason} ${[...row.before, ...row.after].map(unitText).join(" ")} ${row.citations.map((c) => c.quote).join(" ")}` })) : (report.risks ?? []).map((row) => ({ id: row.id, status: row.kind, review: row.review_required, text: `${row.id} ${row.reason} ${row.units.map(unitText).join(" ")} ${row.refs.map(clauseText).join(" ")} ${row.citations.map((c) => c.quote).join(" ")}` }));
    return rows.map((row) => ({ ...row, text: row.text.toLocaleLowerCase("ru") }));
  }, [report, section, index]);
  const visibleIds = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("ru");
    return searchable.filter((row) => (filter === "all" || row.status === filter) && (!reviewOnly || row.review) && (!q || row.text.includes(q))).map((row) => row.id);
  }, [searchable, query, filter, reviewOnly]);
  const safePage = Math.min(page, Math.max(0, Math.ceil(visibleIds.length / PAGE_SIZE) - 1));
  const pageIds = new Set(visibleIds.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE));
  const changeSection = (value: Section) => { setSection(value); setFilter("all"); setQuery(""); setReviewOnly(false); setPage(0); setExpanded(null); };
  const jump = (target: Section, id: string) => {
    const rows = target === "findings" ? report.findings : target === "units" ? report.unit_changes ?? [] : report.risks ?? [];
    const position = rows.findIndex((row) => row.id === id);
    if (position < 0) { setNavigationError(`Ссылка ${id} не разрешается: запись отсутствует в сохранённом отчёте.`); return; }
    setNavigationError(null); changeSection(target); setPage(Math.floor(position / PAGE_SIZE)); setExpanded(id);
    setFocus((previous) => ({ section: target, id, serial: (previous?.serial ?? 0) + 1 }));
  };
  const link = (target: Section, id: string) => <button key={`${target}-${id}`} type="button" className={button} onClick={() => jump(target, id)}>{target === "findings" ? "Функция" : target === "units" ? "Подразделение" : "Риск"}: {id}</button>;
  const labels: Record<string, string> = section === "findings" ? STATUS_LABEL : section === "units" ? unitLabels : riskLabels;
  const options = section === "findings" ? STATUS_ORDER : Object.keys(labels);
  const unitsAssessed = report.unit_changes !== undefined && (report.agent != null || report.unit_changes.length > 0);
  const risksAssessed = report.risks !== undefined && (report.agent != null || report.risks.length > 0);
  const notAssessed = section === "units" ? !unitsAssessed : section === "risks" ? !risksAssessed : false;

  return <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
    <div className="min-w-0 space-y-4">
      <section className={panel} aria-label="Режим и объём анализа">
        <h2 className="text-sm font-semibold text-neutral-100">{report.mode === "deterministic" ? "Детерминированный отчёт" : "Отчёт с участием модели"}</h2>
        <p className="mt-1 text-xs text-neutral-400">Рекомендательный анализ только переданных документов. Точная цитата подтверждает источник, но не правильность смыслового вывода. Учёт извлечённых пунктов не доказывает полноту извлечения или отсутствие рисков.</p>
        {report.agent ? <div className="mt-3 space-y-2 text-xs"><p className="text-amber-200">Агент: {agentLabels[report.agent.status]}</p><p className="break-words text-neutral-400">Модель: {report.agent.model ?? "не указана"} · ходов: {report.agent.turns} · вызовов инструментов: {report.agent.tool_calls}</p><p className="whitespace-pre-wrap break-words text-neutral-300">Причина остановки: {report.agent.stop_reason || "не указана"}</p><p className="text-neutral-400">Функциональных выводов в исследованном подмножестве: {investigatedKnown}/{report.findings.length}. Вне указанного подмножества: {report.findings.length - investigatedKnown}. Статус «завершён» не означает проверку всего комплекта моделью; полнота проверки подразделений и рисков этим счётчиком не измеряется.</p><details><summary className="cursor-pointer text-neutral-300">Исследованное подмножество ({investigated.size})</summary><div className="mt-2 flex max-h-48 flex-wrap gap-1 overflow-y-auto">{investigated.size ? [...investigated].map((id) => link("findings", id)) : <p className="text-neutral-500">Исследованные функциональные выводы не указаны.</p>}</div></details></div> : <p className="mt-2 text-xs text-amber-200">В этом отчёте нет данных выполнения агента: объём его исследования не оценивался.{llmRequested === true ? " Запрос помощи модели в текущей сессии не подтверждает её выполнение." : ""}</p>}
      </section>
      <div className="grid gap-3 md:grid-cols-2">
        <section className={panel}><h2 className="mb-2 text-sm font-medium text-neutral-200">Документы ({report.documents.length})</h2><ul className="max-h-56 space-y-2 overflow-y-auto">{report.documents.map((doc) => <li key={doc.doc} className="break-words text-xs text-neutral-300"><span className="font-mono text-amber-200">{doc.doc}</span> · {doc.edition === "before" ? "До" : "После"} · {doc.source}<details className="mt-1 text-[10px] text-neutral-500"><summary className="cursor-pointer">Идентификатор и контрольная сумма</summary><p className="break-all">{doc.doc_id}<br />SHA-256: {doc.sha256}</p></details></li>)}</ul></section>
        <section className={panel}><h2 className="mb-2 text-sm font-medium text-neutral-200">Охват извлечённых функций</h2><dl className="space-y-2 text-xs text-neutral-400"><div className="flex justify-between"><dt>До: учтено / всего</dt><dd>{report.coverage.before_accounted}/{report.coverage.before_total}</dd></div><div className="flex justify-between"><dt>После: учтено / всего</dt><dd>{report.coverage.after_accounted}/{report.coverage.after_total}</dd></div><div className="flex justify-between"><dt>Неопределённых ссылок</dt><dd>{report.coverage.unresolved}</dd></div></dl><p className="mt-2 text-[11px] text-neutral-500">«Учтено» включает неоднозначные сопоставления и не означает экспертную проверку.</p></section>
      </div>
      {!!report.warnings.length && <section className="rounded-lg border border-amber-800 bg-amber-950/25 p-3"><h2 className="mb-2 text-sm font-medium text-amber-300">Предупреждения и ограничения ({report.warnings.length})</h2><ul className="max-h-64 list-disc space-y-1 overflow-y-auto pl-4 text-xs text-amber-100">{report.warnings.map((warning, i) => <li key={i} className="whitespace-pre-wrap break-words">{warning}</li>)}</ul></section>}
      <section className={panel}><h2 className="mb-2 text-sm font-semibold text-neutral-200">Аналитическое заключение</h2>{report.conclusion.length ? <ol className="max-h-96 space-y-3 overflow-y-auto">{report.conclusion.map((item, i) => <li key={i} className="space-y-2"><p className="whitespace-pre-wrap break-words text-sm text-neutral-200">{i + 1}. {item.text}</p><div className="flex flex-wrap gap-1">{item.finding_ids.map((id) => link("findings", id))}{(item.unit_change_ids ?? []).map((id) => link("units", id))}{(item.risk_ids ?? []).map((id) => link("risks", id))}</div><Evidence citations={item.citations} index={index} onOpen={setSelection} /></li>)}</ol> : <p className="text-xs text-neutral-500">Заключение не предоставлено. Это не подтверждает отсутствие проблем.</p>}</section>
      {navigationError && <p role="alert" className="rounded border border-red-800 p-3 text-xs text-red-200">{navigationError}</p>}
      <section ref={reportStart} className="min-w-0 overflow-hidden rounded-lg border border-neutral-800 bg-neutral-900/40" aria-label="Результаты анализа">
        <div className="space-y-3 border-b border-neutral-800 p-3">
          <nav aria-label="Разделы отчёта" className="flex flex-wrap gap-2">{([['findings', 'Функции', report.findings.length], ['units', 'Подразделения', unitsAssessed ? report.unit_changes?.length : undefined], ['risks', 'Межподразделенческие риски', risksAssessed ? report.risks?.length : undefined]] as const).map(([value, label, count]) => <button key={value} type="button" aria-current={section === value ? "page" : undefined} onClick={() => changeSection(value)} className={`${button} ${section === value ? "border-amber-600 bg-amber-950/30" : ""}`}>{label} · {count ?? "не оценивалось"}</button>)}</nav>
          <p className="text-xs text-neutral-400">{section === "findings" ? "Потеря — гипотеза об отсутствии преемника в переданном комплекте, не доказательство утраты. Дублирование функций и межподразделенческие риски учитываются отдельно, без суммирования." : section === "units" ? "Сохранение, создание и реорганизация требуют источников. Связи N:M сохраняются целиком; отсутствие преемника само по себе не означает ликвидацию." : "Рекомендательные риски, а не доказанные нарушения или юридические заключения. Проверяйте обе обязанности и основание несовместимости. Пустой список не означает отсутствие риска."}</p>
          <div className="flex flex-wrap gap-1"><button type="button" className={button} aria-pressed={filter === "all"} onClick={() => { setFilter("all"); setPage(0); }}>Все · {searchable.length}</button>{options.map((value) => <button key={value} type="button" aria-pressed={filter === value} className={`${button} ${filter === value ? "border-amber-600 bg-amber-950/30" : ""}`} title={section === "findings" ? STATUS_MEANING[value as FindingStatus] : undefined} onClick={() => { setFilter(value); setPage(0); }}>{labels[value]} · {counts[value] ?? 0}</button>)}</div>
          <div className="flex flex-wrap gap-3"><label className="flex min-w-48 flex-1 items-center gap-2 rounded border border-neutral-700 px-2"><Search size={14} className="text-neutral-500" /><input aria-label="Поиск по результатам" value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} placeholder="Пункт, подразделение, текст, основание…" className="w-full bg-transparent py-1.5 text-xs text-neutral-200 outline-none" /></label><label className="flex items-center gap-2 text-xs text-neutral-400"><input type="checkbox" checked={reviewOnly} onChange={(event) => { setReviewOnly(event.target.checked); setPage(0); }} className="accent-amber-500" />Только требующие проверки</label></div>
        </div>
        {notAssessed ? <p className="p-4 text-sm text-amber-200">Этот раздел не оценивался: поле отсутствует или выполнение Stage 3 не подтверждено. Это не означает отсутствия изменений или рисков.</p> : !visibleIds.length ? <p className="p-4 text-xs text-neutral-400">{searchable.length ? "Нет записей для выбранных фильтров." : "Записи не предоставлены. Пустой список не подтверждает отсутствие изменений, потерь или рисков."}</p> : <div className="overflow-x-auto">
          {section === "findings" && <table className="w-full min-w-[32rem] text-left text-xs"><caption className="sr-only">Сопоставление функций; откройте строку для обеих редакций и источников</caption><thead className="border-b border-neutral-800 text-neutral-500"><tr><th className="p-3">Статус / проверка</th><th className="p-3">До → после</th><th className="p-3">Основание и источники</th></tr></thead><tbody>{report.findings.filter((finding) => pageIds.has(finding.id)).map((finding) => <tr key={finding.id} id={`audit-findings-${finding.id}`} className={`border-b border-neutral-800 align-top ${focus?.section === "findings" && focus.id === finding.id ? "bg-sky-950/20" : ""}`}><td className="w-44 space-y-2 p-3"><StatusBadge status={finding.status} /><p className="break-all font-mono text-neutral-500">{finding.id}</p><ReviewLabel required={finding.review_required} /><p className="text-[10px] text-neutral-500">{methodLabels[finding.method]}</p><p className="text-[10px] text-neutral-400">{report.agent ? investigated.has(finding.id) ? "В подмножестве агента" : "Не включено в подмножество агента" : "Исследование агентом не оценивалось"}</p></td><td className="w-28 p-3 text-neutral-300">{finding.before.length} → {finding.after.length}<div className="mt-2 space-y-1">{[...finding.before, ...finding.after].map((ref, i) => <button key={i} type="button" className="block break-all text-left font-mono text-[11px] text-amber-200 hover:underline" onClick={() => setSelection({ ...ref, quote: finding.citations.find((c) => c.doc === ref.doc && c.clause_id === ref.clause_id)?.quote ?? null })}>{ref.doc} §{ref.clause_id}</button>)}</div></td><td className="p-3"><details open={expanded === finding.id} onToggle={(event) => { if (event.currentTarget.open) setExpanded(finding.id); else setExpanded((current) => current === finding.id ? null : current); }}><summary className="cursor-pointer whitespace-pre-wrap break-words text-neutral-200">{finding.reason || "Открыть сравнение и источники"}</summary><div className="mt-3"><FindingDetail finding={finding} index={index} onOpen={setSelection} /></div></details>{!!related.byFinding.get(finding.id)?.length && <div className="mt-2 space-y-1"><p className="text-[10px] text-neutral-500">Риски с общими источниками (не отдельный суммарный счётчик):</p><div className="flex flex-wrap gap-1">{related.byFinding.get(finding.id)!.map((id) => link("risks", id))}</div></div>}</td></tr>)}</tbody></table>}
          {section === "units" && <table className="w-full min-w-[34rem] text-left text-xs"><caption className="sr-only">Преемственность подразделений N:M</caption><thead className="border-b border-neutral-800 text-neutral-500"><tr><th className="p-3">Классификация</th><th className="p-3">До</th><th className="p-3">После</th><th className="p-3">Основание</th></tr></thead><tbody>{(report.unit_changes ?? []).filter((row) => pageIds.has(row.id)).map((row) => <tr key={row.id} id={`audit-units-${row.id}`} className={`border-b border-neutral-800 align-top ${focus?.section === "units" && focus.id === row.id ? "bg-sky-950/20" : ""}`}><td className="space-y-2 p-3"><p className="font-medium text-amber-200">{unitLabels[row.status]}</p><p className="font-mono text-neutral-500">{row.id}</p><p className="text-neutral-300">{row.before.length} → {row.after.length}</p><ReviewLabel required={row.review_required} /><p className="text-[10px] text-neutral-500">{methodLabels[row.method]}</p></td><td className="p-3"><UnitReferences refs={row.before} index={index} onOpen={setSelection} expected="before" structural /></td><td className="p-3"><UnitReferences refs={row.after} index={index} onOpen={setSelection} expected="after" structural /></td><td className="min-w-48 space-y-2 p-3"><p className="whitespace-pre-wrap break-words text-neutral-300">{row.reason}</p><Evidence citations={row.citations} index={index} onOpen={setSelection} /></td></tr>)}</tbody></table>}
          {section === "risks" && <table className="w-full min-w-[34rem] text-left text-xs"><caption className="sr-only">Потенциальные межподразделенческие риски</caption><thead className="border-b border-neutral-800 text-neutral-500"><tr><th className="p-3">Тип риска</th><th className="p-3">Подразделения / роли после</th><th className="p-3">Обязанности и основания</th></tr></thead><tbody>{(report.risks ?? []).filter((row) => pageIds.has(row.id)).map((row) => <tr key={row.id} id={`audit-risks-${row.id}`} className={`border-b border-neutral-800 align-top ${focus?.section === "risks" && focus.id === row.id ? "bg-sky-950/20" : ""}`}><td className="w-44 space-y-2 p-3"><p className="font-medium text-orange-200">{riskLabels[row.kind]}</p><p className="break-all font-mono text-neutral-500">{row.id}</p><ReviewLabel required={row.review_required} /><p className="text-[10px] text-neutral-500">{methodLabels[row.method]} · Рекомендательный вывод</p></td><td className="p-3"><UnitReferences refs={row.units} index={index} onOpen={setSelection} expected="after" /></td><td className="min-w-56 space-y-3 p-3"><p className="whitespace-pre-wrap break-words text-neutral-300">{row.reason}</p><ClauseReferences refs={row.refs} citations={row.citations} index={index} onOpen={setSelection} expected="after" /><Evidence citations={row.citations} index={index} onOpen={setSelection} />{!!related.byRisk.get(row.id)?.length && <div className="space-y-1"><p className="text-[10px] text-neutral-500">Выводы о функциях с общими источниками; не суммировать автоматически:</p><div className="flex flex-wrap gap-1">{related.byRisk.get(row.id)!.map((id) => link("findings", id))}</div></div>}</td></tr>)}</tbody></table>}
        </div>}
        <Pagination page={safePage} total={visibleIds.length} onChange={(value) => { setPage(value); setExpanded(null); reportStart.current?.scrollIntoView({ block: "start" }); }} />
      </section>
    </div>
    <aside aria-label="Просмотр первоисточника" className={`${selection ? "fixed inset-x-2 bottom-2 z-40 flex max-h-[75vh]" : "hidden"} min-h-0 flex-col overflow-hidden rounded-xl border border-neutral-700 bg-neutral-900 shadow-2xl xl:sticky xl:inset-auto xl:top-4 xl:z-auto xl:flex xl:max-h-[calc(100vh-2rem)] xl:self-start`}><ClauseViewer selection={selection} index={index} onOpen={setSelection} onClose={() => setSelection(null)} /></aside>
  </div>;
}
