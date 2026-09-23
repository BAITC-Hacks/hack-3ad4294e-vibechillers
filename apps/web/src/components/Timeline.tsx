"use client";

import { useState } from "react";
import {
  BookOpenText,
  ChevronRight,
  CircleAlert,
  CirclePlus,
  Loader2,
  XCircle,
  CheckCircle2,
} from "lucide-react";
import type { CitationRow, ErrorRow, StatusRow, ToolRow } from "../lib/timeline";

function preview(v: unknown, max = 160): string {
  const s = typeof v === "string" ? v : JSON.stringify(v);
  if (s === undefined) return "";
  return s.length > max ? `${s.slice(0, max)}…` : s;
}

function Disclosure({
  open,
  onToggle,
  children,
}: {
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className="flex w-full items-center gap-1.5 text-left"
    >
      <ChevronRight
        size={13}
        className={`shrink-0 text-neutral-400 transition-transform ${open ? "rotate-90" : ""}`}
      />
      {children}
    </button>
  );
}

function auditStatusCaption(message: string): string | null {
  const ingested = /^Ingested (before|after) document .+ from (.+) \(doc_id .+, (\d+) text blocks\)$/.exec(message);
  if (ingested) {
    return `Извлечён текст: ${ingested[2]}. Редакция «${ingested[1] === "before" ? "до" : "после"}», блоков: ${ingested[3]}.`;
  }
  if (message === "Building deterministic report: parsing clauses, aligning functions, verifying citations") {
    return "Формируем алгоритмический отчёт: разбираем пункты, сопоставляем функции и проверяем цитаты.";
  }
  if (message.startsWith("Deterministic report ready: ")) {
    return "Алгоритмический отчёт готов. Сопоставления и охват доступны в результатах.";
  }
  if (message === "LLM adjudication of ambiguous findings requested") {
    return "Запрошена проверка неоднозначных сопоставлений моделью. Запрос не подтверждает её выполнение.";
  }
  if (message.startsWith("Report mode: deterministic; ")) return "Режим отчёта: алгоритмическое сравнение без участия модели.";
  if (message.startsWith("Report mode: llm_assisted; ")) return "Режим отчёта: с участием модели. Область проверки указана в отчёте.";
  return null;
}

export function StatusLine({ row }: { row: StatusRow }) {
  const caption = auditStatusCaption(row.message);
  return (
    <div className="flex items-start gap-3 rounded-lg bg-neutral-950/40 px-3 py-3 text-xs leading-relaxed text-neutral-300">
      <span className="shrink-0 tabular-nums text-neutral-400">#{row.seq}</span>
      <div className="min-w-0">
        <p className="whitespace-pre-wrap break-words">{caption ?? row.message}</p>
        {caption && (
          <details className="mt-2 text-neutral-400">
            <summary className="cursor-pointer rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400">Исходное событие</summary>
            <p className="mt-2 whitespace-pre-wrap break-words text-neutral-300">{row.message}</p>
          </details>
        )}
      </div>
    </div>
  );
}

export function ToolRowView({ row, active = true }: { row: ToolRow; active?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`rounded-xl border px-3 py-3 text-xs leading-relaxed ${
      row.ok === false ? "border-neutral-800 bg-red-950/30" : "border-neutral-800 bg-neutral-900/70"
    }`}>
      <Disclosure open={open} onToggle={() => setOpen((v) => !v)}>
        {!row.done && active ? (
          <Loader2 size={13} className="shrink-0 animate-spin text-sky-400" />
        ) : row.ok === true ? (
          <CheckCircle2 size={13} className="shrink-0 text-emerald-500" />
        ) : row.ok === false ? (
          <XCircle size={13} className="shrink-0 text-red-400" />
        ) : (
          <CircleAlert size={13} className="shrink-0 text-amber-400" />
        )}
        <span className="break-all font-mono font-medium text-neutral-200">{row.name}</span>
        <span className="min-w-0 truncate font-mono text-neutral-400">{preview(row.args, 80)}</span>
        <span className="ml-auto flex shrink-0 items-center gap-2 pl-2 tabular-nums">
          {row.ms !== null && <span className="text-neutral-400">{Math.round(row.ms)} мс</span>}
          {!row.done && <span className="text-sky-400">{active ? "выполняется…" : "нет результата"}</span>}
        </span>
      </Disclosure>
      {row.reason && (
        <p className="mt-2 whitespace-pre-wrap break-words text-neutral-300">Основание: {row.reason}</p>
      )}
      {open && (
        <div className="mt-3 space-y-3 border-t border-neutral-800 pt-3">
          <div>
            <div className="mb-1 text-xs font-medium text-neutral-300">Аргументы</div>
            <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-all font-mono text-xs text-neutral-300">
              {JSON.stringify(row.args, null, 2)}
            </pre>
          </div>
          <div>
            <div className="mb-1 text-xs font-medium text-neutral-300">
              {row.ok === false ? "Ошибка" : "Результат"}
            </div>
            <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-all font-mono text-xs text-neutral-300">
              {row.done ? JSON.stringify(row.result, null, 2) ?? "null" : active ? "Ожидаем результат…" : "Результат отсутствует в журнале."}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export function CitationChip({ row }: { row: CitationRow }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className={`inline-flex max-w-full flex-col rounded-full border px-2.5 py-1 text-xs ${
        open
          ? "items-stretch border-amber-700/60 bg-amber-950/30"
          : "cursor-pointer items-center border-neutral-700 bg-neutral-900 hover:border-amber-700/60"
      }`}
      onClick={() => setOpen((v) => !v)}
      role="button"
      tabIndex={0}
      aria-expanded={open}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setOpen((v) => !v);
        }
      }}
    >
      <span className="flex items-center gap-1.5">
        <BookOpenText size={12} className="shrink-0 text-amber-400" />
        <span className="truncate font-mono text-neutral-200">
          {row.source || row.docId}
        </span>
        {row.page !== null && (
          <span className="shrink-0 text-neutral-400">стр. {row.page}</span>
        )}
        <CirclePlus size={11} className="shrink-0 text-neutral-500" />
      </span>
      {open && (
        <span className="mt-1 block max-w-md whitespace-pre-wrap text-[11px] leading-relaxed text-neutral-300">
          {row.snippet || "[текст цитаты отсутствует]"}
        </span>
      )}
    </div>
  );
}

export function ErrorRowView({ row }: { row: ErrorRow }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-neutral-800 bg-red-950/40 p-4 text-sm leading-relaxed text-red-200">
      <CircleAlert size={14} className="mt-0.5 shrink-0 text-red-400" />
      <div>
        <div className="font-medium">
          {row.recoverable ? "Ошибка с продолжением работы" : "Ошибка"}
        </div>
        <div className="mt-0.5 whitespace-pre-wrap break-words text-red-300">
          {row.message}
        </div>
      </div>
    </div>
  );
}
