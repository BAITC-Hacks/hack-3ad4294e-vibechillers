"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  BookOpenText,
  ChevronLeft,
  ChevronRight,
  Cpu,
  Eye,
  FileText,
  ListChecks,
  Search,
  Sparkles,
  TriangleAlert,
  X,
} from "lucide-react";
import type {
  Citation,
  Clause,
  ClauseRef,
  Finding,
  FindingStatus,
  Report,
} from "../lib/api";
import {
  STATUS_MEANING,
  STATUS_ORDER,
  STATUS_STYLE,
  buildReportIndex,
  checkCitation,
  clauseAncestors,
  clauseUnits,
  refKey,
  unitChain,
  type ReportIndex,
} from "../lib/audit";

interface ClauseSelection {
  doc: string;
  clause_id: string;
  /** Exact quote to highlight; null opens the clause without a highlight. */
  quote: string | null;
}

type OpenClause = (sel: ClauseSelection) => void;

function clip(s: string, max: number): string {
  return s.length > max ? `${s.slice(0, max)}…` : s;
}

function StatusBadge({ status }: { status: FindingStatus }) {
  return (
    <span
      title={STATUS_MEANING[status]}
      className={`inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLE[status]}`}
    >
      {status}
    </span>
  );
}

function CitationLink({
  citation,
  index,
  onOpen,
  active,
}: {
  citation: Citation;
  index: ReportIndex;
  onOpen: OpenClause;
  active: boolean;
}) {
  const check = checkCitation(index, citation);
  return (
    <button
      type="button"
      onClick={() =>
        onOpen({
          doc: citation.doc,
          clause_id: citation.clause_id,
          quote: citation.quote,
        })
      }
      title={check.ok ? citation.quote : `Unverified citation: ${check.reason}`}
      className={`inline-flex max-w-full items-center gap-1.5 rounded-full border px-2 py-0.5 text-left text-[11px] transition-colors ${
        !check.ok
          ? "border-red-800 bg-red-950/40 text-red-200 hover:bg-red-950/70"
          : active
            ? "border-amber-600 bg-amber-950/50 text-amber-100"
            : "border-neutral-700 bg-neutral-900 text-neutral-300 hover:border-amber-700/70"
      }`}
    >
      {check.ok ? (
        <BookOpenText size={11} className="shrink-0 text-amber-400" />
      ) : (
        <TriangleAlert size={11} className="shrink-0 text-red-400" />
      )}
      <span className="shrink-0 font-mono">
        {citation.doc} §{citation.clause_id}
      </span>
      <span className="min-w-0 truncate text-neutral-400">
        «{clip(citation.quote, 70)}»
      </span>
    </button>
  );
}

function RefList({
  side,
  refs,
  finding,
  index,
  onOpen,
  selection,
}: {
  side: "Before" | "After";
  refs: ClauseRef[];
  finding: Finding;
  index: ReportIndex;
  onOpen: OpenClause;
  selection: ClauseSelection | null;
}) {
  return (
    <div className="min-w-0">
      <div className="mb-1 text-[10px] uppercase tracking-wide text-neutral-500">
        {side}
      </div>
      {refs.length === 0 ? (
        <div className="rounded-md border border-dashed border-neutral-800 px-2 py-1.5 text-[11px] text-neutral-600">
          {side === "After" && finding.status === "missing"
            ? "No supported successor in the supplied after set"
            : side === "Before" && finding.status === "added"
              ? "No supported predecessor in the before set"
              : "none"}
        </div>
      ) : (
        <ul className="space-y-1.5">
          {refs.map((ref) => {
            const clause = index.clauses.get(refKey(ref.doc, ref.clause_id));
            const quote =
              finding.citations.find(
                (c) => c.doc === ref.doc && c.clause_id === ref.clause_id
              )?.quote ?? null;
            const active =
              selection?.doc === ref.doc &&
              selection.clause_id === ref.clause_id;
            if (!clause) {
              return (
                <li
                  key={refKey(ref.doc, ref.clause_id)}
                  className="rounded-md border border-red-900 bg-red-950/30 px-2 py-1.5 text-[11px] text-red-300"
                >
                  <span className="font-mono">
                    {ref.doc} §{ref.clause_id}
                  </span>{" "}
                  does not resolve to a clause in this report
                </li>
              );
            }
            const parent = clause.parent_id
              ? index.clauses.get(refKey(clause.doc, clause.parent_id))
              : undefined;
            const units = clauseUnits(index, clause);
            return (
              <li key={refKey(ref.doc, ref.clause_id)}>
                <button
                  type="button"
                  onClick={() =>
                    onOpen({ doc: ref.doc, clause_id: ref.clause_id, quote })
                  }
                  className={`w-full rounded-md border px-2 py-1.5 text-left text-xs transition-colors ${
                    active
                      ? "border-amber-600/80 bg-amber-950/30"
                      : "border-neutral-800 bg-neutral-900/70 hover:border-neutral-600"
                  }`}
                >
                  <div className="flex items-baseline gap-1.5">
                    <span className="rounded bg-neutral-800 px-1 font-mono text-[10px] text-neutral-400">
                      {clause.doc}
                    </span>
                    <span className="font-mono font-medium text-neutral-100">
                      §{clause.clause_id}
                    </span>
                    <span className="text-[10px] text-neutral-500">
                      {clause.kind}
                    </span>
                  </div>
                  <div className="mt-0.5 line-clamp-3 break-words leading-snug text-neutral-300">
                    {clause.text}
                  </div>
                  {(parent || units.length > 0) && (
                    <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5 text-[10px] text-neutral-500">
                      {parent && (
                        <span className="min-w-0 truncate">
                          in §{parent.clause_id} {clip(parent.text, 60)}
                        </span>
                      )}
                      {units.map((u) => (
                        <span
                          key={u.unit_id}
                          className="rounded border border-neutral-700 px-1 text-neutral-400"
                        >
                          {u.kind}: {clip(u.name, 50)}
                        </span>
                      ))}
                    </div>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function FindingCard({
  finding,
  index,
  onOpen,
  selection,
  focused,
}: {
  finding: Finding;
  index: ReportIndex;
  onOpen: OpenClause;
  selection: ClauseSelection | null;
  focused: boolean;
}) {
  return (
    <article
      id={`finding-${finding.id}`}
      className={`scroll-mt-4 rounded-lg border bg-neutral-900/50 p-2.5 ${
        focused ? "border-sky-600 ring-1 ring-sky-600/50" : "border-neutral-800"
      }`}
    >
      <header className="flex flex-wrap items-center gap-1.5">
        <StatusBadge status={finding.status} />
        <span className="font-mono text-[11px] text-neutral-400">
          {finding.id}
        </span>
        <span
          className="rounded border border-neutral-800 px-1.5 text-[10px] text-neutral-500"
          title="How this finding was established"
        >
          {finding.method}
        </span>
        {finding.review_required && (
          <span className="ml-auto inline-flex items-center gap-1 rounded-full border border-amber-700 bg-amber-950/40 px-2 py-0.5 text-[10px] font-medium text-amber-300">
            <Eye size={10} />
            review required
          </span>
        )}
      </header>
      <p className="mt-1.5 whitespace-pre-wrap break-words text-xs leading-relaxed text-neutral-300">
        {finding.reason}
      </p>
      <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
        <RefList
          side="Before"
          refs={finding.before}
          finding={finding}
          index={index}
          onOpen={onOpen}
          selection={selection}
        />
        <RefList
          side="After"
          refs={finding.after}
          finding={finding}
          index={index}
          onOpen={onOpen}
          selection={selection}
        />
      </div>
      {["Function evidence", "Context sources"].map((label, group) => {
        const citations = finding.citations.filter((citation) => {
          const direct = [...finding.before, ...finding.after].some(
            (ref) => ref.doc === citation.doc && ref.clause_id === citation.clause_id
          );
          return group === 0 ? direct : !direct;
        });
        return citations.length > 0 && (
          <div key={label} className="mt-2">
            <div className="mb-1 text-[10px] uppercase tracking-wide text-neutral-500">{label}</div>
            <div className="flex flex-wrap gap-1">
              {citations.map((c, i) => (
                <CitationLink
                  key={`${refKey(c.doc, c.clause_id)}-${i}`}
                  citation={c}
                  index={index}
                  onOpen={onOpen}
                  active={
                    selection?.doc === c.doc &&
                    selection.clause_id === c.clause_id &&
                    selection.quote === c.quote
                  }
                />
              ))}
            </div>
          </div>
        );
      })}
    </article>
  );
}

function ClauseViewer({
  selection,
  index,
  onOpen,
  onClose,
}: {
  selection: ClauseSelection | null;
  index: ReportIndex;
  onOpen: OpenClause;
  onClose: () => void;
}) {
  const markRef = useRef<HTMLElement>(null);
  const clause: Clause | null = selection
    ? (index.clauses.get(refKey(selection.doc, selection.clause_id)) ?? null)
    : null;
  const check =
    selection && selection.quote !== null
      ? checkCitation(index, {
          doc: selection.doc,
          clause_id: selection.clause_id,
          quote: selection.quote,
        })
      : null;

  useEffect(() => {
    markRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selection]);

  if (selection === null) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-xs text-neutral-600">
        Click a citation or a clause reference to open the preserved clause
        text with its quote highlighted.
      </div>
    );
  }

  const doc = index.docs.get(selection.doc);
  const siblings = clause ? (index.byDoc.get(clause.doc) ?? []) : [];
  const pos = clause ? siblings.indexOf(clause) : -1;
  const prev = pos > 0 ? siblings[pos - 1] : null;
  const next = pos !== -1 && pos < siblings.length - 1 ? siblings[pos + 1] : null;
  const ancestors = clause ? clauseAncestors(index, clause) : [];
  const units = clause ? clauseUnits(index, clause) : [];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b border-neutral-800 px-3 py-2">
        <FileText size={13} className="shrink-0 text-amber-400" />
        <span className="rounded bg-neutral-800 px-1.5 font-mono text-[11px] text-neutral-300">
          {selection.doc}
        </span>
        {doc && (
          <span
            className="min-w-0 truncate text-[11px] text-neutral-500"
            title={`${doc.source} · sha256 ${doc.sha256}`}
          >
            {doc.edition} · {doc.source}
          </span>
        )}
        <button
          type="button"
          onClick={onClose}
          aria-label="Close clause"
          className="ml-auto shrink-0 rounded p-1 text-neutral-500 hover:bg-neutral-800 hover:text-neutral-200"
        >
          <X size={14} />
        </button>
      </div>
      <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto p-3 text-xs">
        {clause === null ? (
          <div className="rounded-md border border-red-800 bg-red-950/40 px-2.5 py-2 text-red-200">
            No clause <span className="font-mono">§{selection.clause_id}</span>{" "}
            in document <span className="font-mono">{selection.doc}</span> of
            this report. The reference cannot be verified.
          </div>
        ) : (
          <>
            {ancestors.length > 0 && (
              <nav className="flex flex-wrap items-center gap-1 text-[11px] text-neutral-500">
                {ancestors.map((a) => (
                  <span key={a.clause_id} className="flex items-center gap-1">
                    <button
                      type="button"
                      title={a.text}
                      onClick={() =>
                        onOpen({ doc: a.doc, clause_id: a.clause_id, quote: null })
                      }
                      className="font-mono hover:text-neutral-200"
                    >
                      §{a.clause_id}
                    </button>
                    <ChevronRight size={10} />
                  </span>
                ))}
              </nav>
            )}
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="font-mono text-sm font-semibold text-neutral-100">
                §{clause.clause_id}
              </span>
              {clause.label !== "" && (
                <span className="font-mono text-neutral-400">
                  label “{clause.label}”
                </span>
              )}
              <span className="rounded border border-neutral-700 px-1.5 text-[10px] text-neutral-400">
                {clause.kind}
              </span>
              <span
                className="text-[10px] text-neutral-600"
                title="Source block order within the document. This is not a Word page number."
              >
                block #{clause.ordinal}
              </span>
            </div>
            {check !== null && !check.ok && (
              <div className="flex items-start gap-1.5 rounded-md border border-red-800 bg-red-950/40 px-2.5 py-2 text-red-200">
                <TriangleAlert size={13} className="mt-0.5 shrink-0 text-red-400" />
                <div>
                  <div className="font-medium">Citation not verified</div>
                  <div className="text-red-300">{check.reason}</div>
                  <div className="mt-1 text-red-300/80">
                    Cited quote: «{selection.quote}»
                  </div>
                </div>
              </div>
            )}
            <div className="whitespace-pre-wrap break-words rounded-md border border-neutral-800 bg-neutral-950/60 p-2.5 text-[13px] leading-relaxed text-neutral-200">
              {check !== null && check.ok ? (
                <>
                  {clause.text.slice(0, check.start)}
                  <mark
                    ref={markRef}
                    className="rounded-sm bg-amber-400/25 px-0.5 text-amber-100 ring-1 ring-amber-500/60"
                  >
                    {clause.text.slice(check.start, check.end)}
                  </mark>
                  {clause.text.slice(check.end)}
                </>
              ) : (
                clause.text
              )}
            </div>
            {ancestors.length > 0 && (
              <section className="space-y-1.5" aria-label="Governing source context">
                <div className="text-[10px] uppercase tracking-wide text-neutral-500">
                  Governing source context
                </div>
                <p className="text-[11px] text-neutral-400">
                  Parent wording may define the role, permission or restriction.
                  It is separate source text, not part of this child clause.
                </p>
                {[...ancestors].reverse().map((parent) => (
                  <div key={parent.clause_id} className="rounded-md border border-neutral-800 p-2">
                    <CitationLink
                      citation={{ doc: parent.doc, clause_id: parent.clause_id, quote: parent.text }}
                      index={index}
                      onOpen={onOpen}
                      active={false}
                    />
                    <p className="mt-1 whitespace-pre-wrap break-words text-neutral-300">
                      {parent.text}
                    </p>
                  </div>
                ))}
              </section>
            )}
            {units.length > 0 && (
              <div className="space-y-1.5">
                <div className="text-[10px] uppercase tracking-wide text-neutral-500">
                  Associated units / roles
                </div>
                <p className="text-[11px] text-neutral-400">
                  A named recipient or delegate is not automatically accountable.
                  Check the defining role and parent sources below.
                </p>
                {units.map((u) => (
                  <div
                    key={u.unit_id}
                    className="rounded-md border border-neutral-800 bg-neutral-900/60 px-2 py-1.5"
                  >
                    <div className="text-neutral-200">
                      {unitChain(index, u)
                        .map((x) => x.name)
                        .join(" › ")}
                      <span className="ml-1.5 text-[10px] text-neutral-500">
                        {u.kind} · {u.unit_id}
                      </span>
                    </div>
                    {u.citations.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {u.citations.map((c, i) => (
                          <CitationLink
                            key={`${refKey(c.doc, c.clause_id)}-${i}`}
                            citation={c}
                            index={index}
                            onOpen={onOpen}
                            active={false}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                disabled={prev === null}
                onClick={() =>
                  prev && onOpen({ doc: prev.doc, clause_id: prev.clause_id, quote: null })
                }
                className="flex items-center gap-1 rounded border border-neutral-800 px-2 py-1 text-[11px] text-neutral-400 hover:border-neutral-600 disabled:opacity-40"
              >
                <ChevronLeft size={11} />
                {prev ? `§${prev.clause_id}` : "start"}
              </button>
              <button
                type="button"
                disabled={next === null}
                onClick={() =>
                  next && onOpen({ doc: next.doc, clause_id: next.clause_id, quote: null })
                }
                className="ml-auto flex items-center gap-1 rounded border border-neutral-800 px-2 py-1 text-[11px] text-neutral-400 hover:border-neutral-600 disabled:opacity-40"
              >
                {next ? `§${next.clause_id}` : "end"}
                <ChevronRight size={11} />
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function CoverageBar({
  label,
  accounted,
  total,
}: {
  label: string;
  accounted: number;
  total: number;
}) {
  const pct = total === 0 ? 0 : Math.min(100, (accounted / total) * 100);
  const full = accounted >= total;
  return (
    <div>
      <div className="flex items-baseline justify-between text-[11px]">
        <span className="text-neutral-400">{label}</span>
        <span className={`tabular-nums ${full ? "text-emerald-300" : "text-amber-300"}`}>
          {accounted}/{total}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-neutral-800">
        <div
          className={`h-full rounded-full ${full ? "bg-emerald-500" : "bg-amber-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Full Function Lineage Auditor report. Every citation resolves locally
 * against `report.clauses` by `(doc, clause_id)`; nothing is fetched and no
 * page numbers are shown.
 */
export function AuditReportView({
  report,
  llmRequested,
}: {
  report: Report;
  /** Whether this session asked for LLM assistance; null for reports opened by run id. */
  llmRequested: boolean | null;
}) {
  const index = useMemo(() => buildReportIndex(report), [report]);
  const [selection, setSelection] = useState<ClauseSelection | null>(null);
  const [statusFilter, setStatusFilter] = useState<FindingStatus | "all">("all");
  const [reviewOnly, setReviewOnly] = useState(false);
  const [query, setQuery] = useState("");
  const [focus, setFocus] = useState<{ id: string; n: number } | null>(null);

  useEffect(() => {
    if (focus === null) return;
    document
      .getElementById(`finding-${focus.id}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focus]);

  const counts = useMemo(() => {
    const c: Partial<Record<FindingStatus, number>> = {};
    for (const f of report.findings) c[f.status] = (c[f.status] ?? 0) + 1;
    return c;
  }, [report.findings]);
  const reviewCount = report.findings.filter((f) => f.review_required).length;

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return report.findings.filter((f) => {
      if (statusFilter !== "all" && f.status !== statusFilter) return false;
      if (reviewOnly && !f.review_required) return false;
      if (q === "") return true;
      if (f.id.toLowerCase().includes(q) || f.reason.toLowerCase().includes(q))
        return true;
      return [...f.before, ...f.after].some((r) => {
        if (r.clause_id.toLowerCase().includes(q)) return true;
        const cl = index.clauses.get(refKey(r.doc, r.clause_id));
        return cl !== undefined && cl.text.toLowerCase().includes(q);
      });
    });
  }, [report.findings, statusFilter, reviewOnly, query, index]);

  const jumpToFinding = (id: string): void => {
    setStatusFilter("all");
    setReviewOnly(false);
    setQuery("");
    setFocus((f) => ({ id, n: (f?.n ?? 0) + 1 }));
  };

  const { coverage } = report;
  const degraded = report.mode === "deterministic";

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
      <div className="min-w-0 space-y-4">
        {/* Mode */}
        {degraded ? (
          <div
            className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-xs ${
              llmRequested
                ? "border-amber-700 bg-amber-950/40 text-amber-200"
                : "border-neutral-700 bg-neutral-900/60 text-neutral-300"
            }`}
          >
            <Cpu size={14} className="mt-0.5 shrink-0" />
            <div>
              <div className="font-medium">
                Deterministic report
                {llmRequested ? " — LLM assistance was unavailable" : ""}
              </div>
              <div className="opacity-80">
                {llmRequested
                  ? "LLM adjudication was requested but did not run; findings come from exact/lexical matching only. The reason is listed under warnings."
                  : "Findings come from exact/lexical matching only; no model adjudication was applied."}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-2 rounded-lg border border-violet-800 bg-violet-950/30 px-3 py-2 text-xs text-violet-200">
            <Sparkles size={14} className="mt-0.5 shrink-0" />
            <div>
              <div className="font-medium">LLM-assisted report</div>
              <div className="opacity-80">
                Findings with method “llm” are model adjudications validated
                against deterministic candidates. Quote validity proves
                provenance, not semantic correctness — review them.
              </div>
            </div>
          </div>
        )}

        {/* Documents + coverage */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-3">
            <div className="mb-2 text-[10px] font-medium uppercase tracking-wide text-neutral-500">
              Documents
            </div>
            <ul className="space-y-1">
              {report.documents.map((d) => (
                <li key={d.doc} className="flex items-center gap-2 text-xs">
                  <span className="rounded bg-neutral-800 px-1.5 font-mono text-[11px] text-neutral-200">
                    {d.doc}
                  </span>
                  <span
                    className={`text-[10px] uppercase ${
                      d.edition === "before" ? "text-sky-400" : "text-emerald-400"
                    }`}
                  >
                    {d.edition}
                  </span>
                  <span className="min-w-0 truncate text-neutral-400" title={d.source}>
                    {d.source}
                  </span>
                  <span
                    className="ml-auto shrink-0 font-mono text-[10px] text-neutral-600"
                    title={`sha256 ${d.sha256}\ndoc_id ${d.doc_id}`}
                  >
                    {d.sha256.slice(0, 10)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="space-y-2 rounded-lg border border-neutral-800 bg-neutral-900/40 p-3">
            <div className="text-[10px] font-medium uppercase tracking-wide text-neutral-500">
              Coverage (unique function clauses)
            </div>
            <CoverageBar
              label="Before accounted"
              accounted={coverage.before_accounted}
              total={coverage.before_total}
            />
            <CoverageBar
              label="After accounted"
              accounted={coverage.after_accounted}
              total={coverage.after_total}
            />
            <div className="flex items-baseline justify-between text-[11px]">
              <span className="text-neutral-400">Unresolved refs</span>
              <span
                className={`tabular-nums ${
                  coverage.unresolved > 0 ? "text-amber-300" : "text-neutral-400"
                }`}
              >
                {coverage.unresolved}
              </span>
            </div>
          </div>
        </div>

        {/* Warnings */}
        {report.warnings.length > 0 && (
          <div className="rounded-lg border border-amber-800/80 bg-amber-950/25 p-3">
            <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-amber-400">
              <TriangleAlert size={12} />
              Warnings ({report.warnings.length})
            </div>
            <ul className="list-disc space-y-0.5 pl-4 text-xs text-amber-100/90">
              {report.warnings.map((w, i) => (
                <li key={i} className="break-words">
                  {w}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Conclusion */}
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-3">
          <div className="mb-2 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-neutral-500">
            <ListChecks size={12} />
            Conclusion
          </div>
          {report.conclusion.length === 0 ? (
            <div className="text-xs text-neutral-500">No conclusion items.</div>
          ) : (
            <ol className="space-y-2.5">
              {report.conclusion.map((item, i) => (
                <li key={i} className="text-sm leading-relaxed text-neutral-200">
                  <div className="whitespace-pre-wrap break-words">{item.text}</div>
                  {(item.finding_ids.length > 0 || item.citations.length > 0) && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {item.finding_ids.map((id) => (
                        <button
                          key={id}
                          type="button"
                          onClick={() => jumpToFinding(id)}
                          className="rounded-full border border-sky-900 bg-sky-950/40 px-2 py-0.5 font-mono text-[11px] text-sky-300 hover:border-sky-700"
                        >
                          {id}
                        </button>
                      ))}
                      {item.citations.map((c, j) => (
                        <CitationLink
                          key={`${refKey(c.doc, c.clause_id)}-${j}`}
                          citation={c}
                          index={index}
                          onOpen={setSelection}
                          active={
                            selection?.doc === c.doc &&
                            selection.clause_id === c.clause_id &&
                            selection.quote === c.quote
                          }
                        />
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>

        {/* Findings */}
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/40">
          <div className="space-y-2 border-b border-neutral-800 p-3">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="mr-1 text-[10px] font-medium uppercase tracking-wide text-neutral-500">
                Findings ({visible.length}/{report.findings.length})
              </span>
              <button
                type="button"
                onClick={() => setStatusFilter("all")}
                className={`rounded-full border px-2 py-0.5 text-[11px] ${
                  statusFilter === "all"
                    ? "border-neutral-500 bg-neutral-800 text-neutral-100"
                    : "border-neutral-800 text-neutral-400 hover:border-neutral-600"
                }`}
              >
                all {report.findings.length}
              </button>
              {STATUS_ORDER.filter((s) => (counts[s] ?? 0) > 0).map((s) => (
                <button
                  key={s}
                  type="button"
                  title={STATUS_MEANING[s]}
                  onClick={() => setStatusFilter(statusFilter === s ? "all" : s)}
                  className={`rounded-full border px-2 py-0.5 text-[11px] ${
                    statusFilter === s
                      ? STATUS_STYLE[s]
                      : "border-neutral-800 text-neutral-400 hover:border-neutral-600"
                  }`}
                >
                  {s} {counts[s]}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="flex min-w-48 flex-1 items-center gap-1.5 rounded-md border border-neutral-800 bg-neutral-950/60 px-2 py-1">
                <Search size={12} className="shrink-0 text-neutral-500" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Filter by clause id, text, reason…"
                  className="w-full bg-transparent text-xs text-neutral-200 placeholder-neutral-600 outline-none"
                />
              </label>
              <label className="flex cursor-pointer items-center gap-1.5 text-[11px] text-neutral-400">
                <input
                  type="checkbox"
                  checked={reviewOnly}
                  onChange={(e) => setReviewOnly(e.target.checked)}
                  className="accent-amber-500"
                />
                review required only ({reviewCount})
              </label>
            </div>
            {statusFilter !== "all" && (
              <div className="text-[11px] text-neutral-500">
                <span className="font-medium text-neutral-300">{statusFilter}</span>:{" "}
                {STATUS_MEANING[statusFilter]}
              </div>
            )}
          </div>
          <div className="space-y-2 p-3">
            {visible.length === 0 ? (
              <div className="py-6 text-center text-xs text-neutral-600">
                No findings match the current filter.
              </div>
            ) : (
              visible.map((f) => (
                <FindingCard
                  key={f.id}
                  finding={f}
                  index={index}
                  onOpen={setSelection}
                  selection={selection}
                  focused={focus?.id === f.id}
                />
              ))
            )}
          </div>
        </div>
      </div>

      {/* Clause viewer: bottom sheet below xl, sticky side panel on xl. */}
      <aside
        className={`${
          selection ? "fixed inset-x-2 bottom-2 z-40 flex max-h-[75vh]" : "hidden"
        } flex-col overflow-hidden rounded-xl border border-neutral-700 bg-neutral-900 shadow-2xl xl:sticky xl:inset-auto xl:bottom-auto xl:top-4 xl:z-auto xl:flex xl:max-h-[calc(100vh-2rem)] xl:self-start xl:border-neutral-800 xl:bg-neutral-900/60 xl:shadow-none`}
      >
        <ClauseViewer
          selection={selection}
          index={index}
          onOpen={setSelection}
          onClose={() => setSelection(null)}
        />
      </aside>
    </div>
  );
}
