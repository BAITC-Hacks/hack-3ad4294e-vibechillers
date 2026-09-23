import type {
  AuditDocument,
  Citation,
  Clause,
  FindingStatus,
  Report,
  Unit,
} from "./api";

/** `(doc, id)` is the only identity a clause or unit has inside a Report. */
export function refKey(doc: string, id: string): string {
  return `${doc}\u0000${id}`;
}

export interface ReportIndex {
  clauses: Map<string, Clause>;
  units: Map<string, Unit>;
  docs: Map<string, AuditDocument>;
  /** Clauses per doc alias, in source order (`ordinal`). */
  byDoc: Map<string, Clause[]>;
}

export function buildReportIndex(report: Report): ReportIndex {
  const clauses = new Map<string, Clause>();
  const byDoc = new Map<string, Clause[]>();
  for (const c of report.clauses) {
    clauses.set(refKey(c.doc, c.clause_id), c);
    const list = byDoc.get(c.doc);
    if (list) list.push(c);
    else byDoc.set(c.doc, [c]);
  }
  for (const list of byDoc.values()) list.sort((a, b) => a.ordinal - b.ordinal);
  const units = new Map<string, Unit>();
  for (const u of report.units) units.set(refKey(u.doc, u.unit_id), u);
  const docs = new Map<string, AuditDocument>();
  for (const d of report.documents) docs.set(d.doc, d);
  return { clauses, units, docs, byDoc };
}

export type CitationCheck =
  | { ok: true; clause: Clause; start: number; end: number }
  | { ok: false; clause: Clause | null; reason: string };

/**
 * Resolve a citation against the report's preserved clauses. Quotes are exact
 * substrings by contract, so the match is verbatim — no normalisation, no
 * fuzzy fallback that could highlight text the report never quoted.
 */
export function checkCitation(index: ReportIndex, c: Citation): CitationCheck {
  const clause = index.clauses.get(refKey(c.doc, c.clause_id)) ?? null;
  if (clause === null) {
    return {
      ok: false,
      clause: null,
      reason: `Пункт ${c.clause_id} отсутствует в документе ${c.doc} этого отчёта`,
    };
  }
  if (c.quote === "") {
    return { ok: false, clause, reason: "Цитата пуста" };
  }
  const start = clause.text.indexOf(c.quote);
  if (start === -1) {
    return {
      ok: false,
      clause,
      reason: "Цитата не совпадает с точным фрагментом сохранённого текста",
    };
  }
  return { ok: true, clause, start, end: start + c.quote.length };
}

/** Ancestors of a clause, root first, following `parent_id` inside its document. */
export function clauseAncestors(index: ReportIndex, clause: Clause): Clause[] {
  const chain: Clause[] = [];
  const seen = new Set<string>([clause.clause_id]);
  let pid = clause.parent_id;
  while (pid !== null && !seen.has(pid)) {
    seen.add(pid);
    const parent = index.clauses.get(refKey(clause.doc, pid));
    if (!parent) break;
    chain.unshift(parent);
    pid = parent.parent_id;
  }
  return chain;
}

/** Units linked to a clause (`unit_ids`), resolved in the clause's document. */
export function clauseUnits(index: ReportIndex, clause: Clause): Unit[] {
  const out: Unit[] = [];
  for (const id of clause.unit_ids) {
    const u = index.units.get(refKey(clause.doc, id));
    if (u) out.push(u);
  }
  return out;
}

/** Unit plus its evidenced parents (`parent_unit_id`), root first. */
export function unitChain(index: ReportIndex, unit: Unit): Unit[] {
  const chain: Unit[] = [unit];
  const seen = new Set<string>([unit.unit_id]);
  let pid = unit.parent_unit_id;
  while (pid !== null && !seen.has(pid)) {
    seen.add(pid);
    const parent = index.units.get(refKey(unit.doc, pid));
    if (!parent) break;
    chain.unshift(parent);
    pid = parent.parent_unit_id;
  }
  return chain;
}

export const STATUS_ORDER: FindingStatus[] = [
  "missing",
  "duplicate",
  "unresolved",
  "changed",
  "moved",
  "added",
  "unchanged",
];

/** Contract meaning of each status (docs/plan.md §3), shown as the legend/tooltips. */
export const STATUS_MEANING: Record<FindingStatus, string> = {
  unchanged: "Текст и контекст сохранены в обеих редакциях",
  changed: "Сопоставление подтверждено, содержание изменилось",
  moved: "Функция сохранена, изменились место или ответственный",
  added: "Подтверждённый предшественник в комплекте «до» не найден",
  missing:
    "Преемник в переданном комплекте «после» не найден — это не доказанная утрата функции",
  duplicate:
    "Возможное пересечение обязанностей, а не просто повторение формулировки",
  unresolved: "Сопоставление неоднозначно; кандидаты сохранены для проверки",
};

export const STATUS_STYLE: Record<FindingStatus, string> = {
  unchanged: "border-neutral-700 bg-neutral-800/60 text-neutral-300",
  changed: "border-sky-800 bg-sky-950/50 text-sky-300",
  moved: "border-violet-800 bg-violet-950/50 text-violet-300",
  added: "border-emerald-800 bg-emerald-950/50 text-emerald-300",
  missing: "border-red-800 bg-red-950/50 text-red-300",
  duplicate: "border-orange-800 bg-orange-950/50 text-orange-300",
  unresolved: "border-amber-700 bg-amber-950/50 text-amber-300",
};

export const STATUS_LABEL: Record<FindingStatus, string> = {
  unchanged: "Без изменений",
  changed: "Изменена",
  moved: "Перенесена",
  added: "Добавлена",
  missing: "Возможная потеря",
  duplicate: "Возможное дублирование",
  unresolved: "Не определено",
};

/** Physical coordinates are reported only when the producer supplied them. */
export function sourceLocation(clause: Clause): string {
  const location = clause.location;
  if (!location) return "Координаты источника не указаны";
  const parts: string[] = [];
  if (location.page !== null) parts.push(`Страница ${location.page}`);
  if (location.block !== null) parts.push(`Блок ${location.block}`);
  if (location.sheet !== null) parts.push(`Лист «${location.sheet}»`);
  if (location.cell_range !== null) parts.push(`Ячейки ${location.cell_range}`);
  return parts.length ? parts.join(" · ") : "Координаты источника не указаны";
}
