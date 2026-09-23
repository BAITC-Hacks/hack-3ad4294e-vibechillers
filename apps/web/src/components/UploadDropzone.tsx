"use client";

import { useRef, useState } from "react";
import { CheckCircle2, FileText, FileUp, Loader2, X, XCircle } from "lucide-react";
import { API_BASE, extractErrorMessage, type UploadOk } from "../lib/api";

interface UploadState {
  phase: "idle" | "busy" | "ok" | "fail";
  ok?: UploadOk;
  error?: string;
  name?: string;
}

export function UploadDropzone() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [state, setState] = useState<UploadState>({ phase: "idle" });

  const send = async (file: File): Promise<void> => {
    setState({ phase: "busy", name: file.name });
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        setState({
          phase: "fail",
          name: file.name,
          error: `HTTP ${res.status}: ${await extractErrorMessage(res)}`,
        });
        return;
      }
      const body: unknown = await res.json();
      setState({ phase: "ok", name: file.name, ok: body as UploadOk });
    } catch (err) {
      setState({
        phase: "fail",
        name: file.name,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  };

  const busy = state.phase === "busy";
  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!busy) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const f = e.dataTransfer.files[0];
          if (f && !busy) void send(f);
        }}
        onClick={() => {
          if (!busy) inputRef.current?.click();
        }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !busy) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        className={`flex cursor-pointer flex-col items-center gap-1.5 rounded-xl border border-dashed px-4 py-5 text-center transition-colors ${
          dragOver
            ? "border-sky-500 bg-sky-950/30"
            : "border-neutral-700 bg-neutral-900/40 hover:border-neutral-500"
        } ${busy ? "pointer-events-none opacity-70" : ""}`}
      >
        {busy ? (
          <Loader2 size={18} className="animate-spin text-sky-400" />
        ) : (
          <FileUp size={18} className="text-neutral-400" />
        )}
        <div className="text-xs text-neutral-300">
          {busy ? `Uploading ${state.name}…` : "Drop a file or click to upload"}
        </div>
        <div className="text-[10px] text-neutral-500">
          POST {API_BASE}/upload
        </div>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (f) void send(f);
          }}
        />
      </div>

      {state.phase === "ok" && state.ok && (
        <div className="mt-2 flex items-start gap-2 rounded-lg border border-emerald-900 bg-emerald-950/30 px-2.5 py-2 text-xs text-emerald-200">
          <CheckCircle2 size={13} className="mt-0.5 shrink-0 text-emerald-400" />
          <div className="min-w-0 break-all">
            <span className="font-mono">{state.ok.doc_id}</span>
            <span className="text-emerald-400">
              {" "}
              · {state.ok.chunks} chunks · {state.ok.pages} pages
            </span>
          </div>
        </div>
      )}
      {state.phase === "fail" && (
        <div className="mt-2 flex items-start gap-2 rounded-lg border border-red-800 bg-red-950/40 px-2.5 py-2 text-xs text-red-200">
          <XCircle size={13} className="mt-0.5 shrink-0 text-red-400" />
          <div className="min-w-0 break-words">{state.error}</div>
        </div>
      )}
    </div>
  );
}

function fmtSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/**
 * Multi-file selector for one side of an audit. Files stay local until the
 * parent submits them; drag-drop and the picker both append, deduplicated.
 */
export function AuditFilePicker({
  label,
  hint,
  files,
  onChange,
  disabled,
  accept = ".docx,.pdf,.xlsx,.txt",
}: {
  label: string;
  hint: string;
  files: File[];
  onChange: (files: File[]) => void;
  disabled: boolean;
  accept?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [selectionError, setSelectionError] = useState<string | null>(null);

  const add = (list: FileList | null): void => {
    if (disabled || !list || list.length === 0) return;
    const rejected: string[] = [];
    const next = [...files];
    for (const f of Array.from(list)) {
      const extension = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
      if (![".docx", ".pdf", ".xlsx", ".txt"].includes(extension)) {
        rejected.push(f.name);
        continue;
      }
      const dup = next.some(
        (g) => g.name === f.name && g.size === f.size && g.lastModified === f.lastModified
      );
      if (!dup) next.push(f);
    }
    setSelectionError(rejected.length
      ? `Не добавлены: ${rejected.join(", ")}. Поддерживаются DOCX, PDF, XLSX и TXT. Старые DOC/XLS сначала сохраните как DOCX/XLSX в Word, Excel или LibreOffice; переименование расширения не конвертирует файл.`
      : null);
    onChange(next);
  };

  // Same stem, different extension on one side = two exports of one edition.
  const stems = new Map<string, string[]>();
  for (const f of files) {
    const dot = f.name.lastIndexOf(".");
    const stem = (dot > 0 ? f.name.slice(0, dot) : f.name).toLowerCase();
    stems.set(stem, [...(stems.get(stem) ?? []), f.name]);
  }
  const twins = [...stems.values()].filter((names) => names.length > 1);

  return (
    <div>
      <div className="mb-1.5 flex items-baseline gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-neutral-300">
          {label}
        </span>
        <span className="text-[10px] text-neutral-500">{hint}</span>
        {files.length > 0 && !disabled && (
          <button
            type="button"
            onClick={() => onChange([])}
            className="ml-auto text-[10px] text-neutral-500 hover:text-neutral-300"
          >
            очистить
          </button>
        )}
      </div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (!disabled) add(e.dataTransfer.files);
        }}
        onClick={() => {
          if (!disabled) inputRef.current?.click();
        }}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        aria-label={`Добавить файлы: ${label}`}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !disabled) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        className={`flex cursor-pointer items-center gap-2 rounded-lg border border-dashed px-3 py-2.5 text-xs transition-colors ${
          dragOver
            ? "border-sky-500 bg-sky-950/30"
            : "border-neutral-700 bg-neutral-900/40 hover:border-neutral-500"
        } ${disabled ? "pointer-events-none opacity-60" : ""}`}
      >
        <FileUp size={15} className="shrink-0 text-neutral-400" />
        <span className="text-neutral-300">
          Перетащите или выберите файлы
        </span>
        <span className="ml-auto font-mono text-[10px] text-neutral-500">
          {accept}
        </span>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={accept}
          disabled={disabled}
          aria-label={`Файлы: ${label}`}
          className="hidden"
          onChange={(e) => {
            add(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
      <p className="mt-1 text-[10px] leading-relaxed text-neutral-500">
        DOCX / XLSX (Office 2007+) и PDF с текстом; TXT — вспомогательный формат.
        DOC / XLS требуют конвертации, не смены расширения.
        Сканированные PDF и произвольные схемы могут требовать ручной проверки.
      </p>
      {selectionError && <p role="alert" className="mt-1 text-xs text-red-300">{selectionError}</p>}
      {files.length > 0 && (
        <ul className="mt-1.5 space-y-1">
          {files.map((f, i) => (
            <li
              key={`${f.name}-${f.size}-${f.lastModified}`}
              className="flex items-center gap-2 rounded-md border border-neutral-800 bg-neutral-900/70 px-2 py-1 text-xs"
            >
              <FileText size={12} className="shrink-0 text-neutral-500" />
              <span className="min-w-0 truncate font-mono text-neutral-200" title={f.name}>
                {f.name}
              </span>
              <span className="ml-auto shrink-0 tabular-nums text-neutral-500">
                {fmtSize(f.size)}
              </span>
              {!disabled && (
                <button
                  type="button"
                  aria-label={`Удалить ${f.name}`}
                  onClick={() => onChange(files.filter((_, j) => j !== i))}
                  className="shrink-0 rounded p-0.5 text-neutral-500 hover:bg-neutral-800 hover:text-neutral-200"
                >
                  <X size={12} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {twins.length > 0 && (
        <div className="mt-1.5 rounded-md border border-amber-800/70 bg-amber-950/30 px-2 py-1.5 text-[11px] leading-snug text-amber-200">
          {twins.map((n) => n.join(" + ")).join("; ")} похожи на несколько экспортов
          одной редакции. Оставьте один источник на редакцию; для Word предпочтителен DOCX.
        </div>
      )}
    </div>
  );
}
