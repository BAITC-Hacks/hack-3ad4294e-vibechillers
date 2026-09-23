"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CircleStop, Download, FolderOpen, GitCompareArrows, ListTree, Loader2, Play } from "lucide-react";
import {
  API_BASE, asReport, fetchAuditReport, fetchRunTrace, readSseEvents, startAudit,
  type Report, type RunEvent,
} from "../lib/api";
import { applyEvent, initialRunState, type RunState } from "../lib/timeline";
import { ErrorRowView, StatusLine, ToolRowView } from "./Timeline";
import { AuditFilePicker } from "./UploadDropzone";
import { AuditReportView } from "./AuditReport";

type Phase = "idle" | "loading" | "running" | "done" | "failed";
type Operation = { controller: AbortController; timeout: number; timedOut: boolean };
const MAX_LOCAL_BYTES = 50 * 1024 * 1024;

function rememberRun(runId: string | null): void {
  const url = new URL(window.location.href);
  if (runId) url.searchParams.set("run", runId);
  else url.searchParams.delete("run");
  window.history.replaceState(null, "", url);
}

/** Also bounds non-fetch work such as reading a local file. */
function abortable<T>(work: Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const abort = () => reject(new Error("Операция остановлена."));
    if (signal.aborted) {
      work.catch(() => undefined);
      abort();
      return;
    }
    signal.addEventListener("abort", abort, { once: true });
    work.then(resolve, reject).finally(() => signal.removeEventListener("abort", abort));
  });
}

function errorMessage(err: unknown, operation: Operation): string {
  if (operation.timedOut) return "Превышено время ожидания. Соединение остановлено. Сохранённый на сервере результат можно открыть по ID запуска.";
  if (operation.controller.signal.aborted) return "Операция остановлена. Это не подтверждает остановку обработки на сервере; результат можно проверить по ID запуска.";
  const message = err instanceof Error ? err.message : String(err);
  if (/404/.test(message)) return "Сохранённый отчёт или журнал не найден (404). Проверьте ID запуска и адрес API.";
  if (/409/.test(message)) return "Отчёт ещё не готов (409). Повторите открытие позже.";
  if (/fetch|network|Failed to fetch/i.test(message)) return `Нет соединения с API (${API_BASE}). Проверьте, что сервер запущен и доступен из браузера.`;
  return `Не удалось выполнить операцию: ${message}`;
}

function downloadReport(report: Report): void {
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `audit-${report.run_id.replace(/[^a-zA-Z0-9_-]/g, "_")}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function AuditWorkspace() {
  const [before, setBefore] = useState<File[]>([]);
  const [after, setAfter] = useState<File[]>([]);
  const [useLlm, setUseLlm] = useState(false);
  const [run, setRun] = useState<RunState>(initialRunState);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [traceNote, setTraceNote] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [llmRequested, setLlmRequested] = useState<boolean | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [lookupId, setLookupId] = useState("");
  const operationRef = useRef<Operation | null>(null);
  const localInputRef = useRef<HTMLInputElement>(null);
  const timelineEndRef = useRef<HTMLDivElement>(null);
  const running = phase === "running";
  const busy = running || phase === "loading";

  const begin = useCallback((nextPhase: "loading" | "running", duration: number): Operation => {
    const previous = operationRef.current;
    if (previous) {
      clearTimeout(previous.timeout);
      previous.controller.abort();
    }
    const operation: Operation = { controller: new AbortController(), timeout: 0, timedOut: false };
    operation.timeout = window.setTimeout(() => {
      operation.timedOut = true;
      operation.controller.abort();
    }, duration);
    operationRef.current = operation;
    setPhase(nextPhase);
    setError(null);
    setTraceNote(null);
    setReport(null);
    setRun(initialRunState);
    setRunId(null);
    setLlmRequested(null);
    return operation;
  }, []);

  const finish = useCallback((operation: Operation): void => {
    clearTimeout(operation.timeout);
    if (operationRef.current === operation) operationRef.current = null;
  }, []);

  useEffect(() => {
    timelineEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [run.rows.length]);
  useEffect(() => {
    if (!running) return;
    const started = performance.now();
    setElapsedMs(0);
    const timer = window.setInterval(() => setElapsedMs(performance.now() - started), 250);
    return () => clearInterval(timer);
  }, [running]);
  useEffect(() => () => {
    const operation = operationRef.current;
    operationRef.current = null;
    if (operation) {
      clearTimeout(operation.timeout);
      operation.controller.abort();
    }
  }, []);

  const openReport = useCallback(async (id: string): Promise<void> => {
    const target = id.trim();
    if (!target) return;
    const operation = begin("loading", 30_000);
    const signal = operation.controller.signal;
    try {
      const [saved, trace] = await Promise.allSettled([
        abortable(fetchAuditReport(target, signal), signal),
        abortable(fetchRunTrace(target, signal), signal),
      ]);
      if (operationRef.current !== operation) return;
      if (signal.aborted && !operation.timedOut) throw new Error("Открытие остановлено.");
      if (saved.status === "rejected") throw saved.reason;
      const rep = saved.value;
      if (rep.run_id !== target) throw new Error("Сервер вернул отчёт другого запуска.");
      setReport(rep);
      setRunId(rep.run_id);
      setLookupId(rep.run_id);
      setPhase("done");
      rememberRun(rep.run_id);
      if (trace.status === "rejected") {
        setTraceNote(`Отчёт открыт, журнал недоступен. ${errorMessage(trace.reason, operation)}`);
      } else if (trace.value.length === 0) {
        setTraceNote("Сохранённый журнал пуст. Действия агента по отчёту не восстанавливаются.");
      } else if (trace.value.some((event) => event.run_id !== rep.run_id)) {
        setTraceNote("Журнал содержит события другого запуска и не показан.");
      } else {
        const replay = [...trace.value].sort((a, b) => a.seq - b.seq).reduce(
          (state, event) => applyEvent(state, event, { includeTokens: false }), initialRunState,
        );
        setRun(replay);
        setTraceNote(replay.finalText === null
          ? "Сохранённый журнал не содержит финального события. Отчёт получен отдельно; полнота журнала не подтверждена."
          : "Сохранённый журнал сервера. Это воспроизведение событий, не новый запуск агента.");
      }
    } catch (err) {
      if (operationRef.current !== operation) return;
      setError(errorMessage(err, operation));
      setPhase("failed");
    } finally {
      finish(operation);
    }
  }, [begin, finish]);

  useEffect(() => {
    const id = new URL(window.location.href).searchParams.get("run");
    if (id) {
      setLookupId(id);
      void openReport(id);
    }
  }, [openReport]);

  const loadLocal = async (file: File): Promise<void> => {
    const operation = begin("loading", 30_000);
    try {
      if (file.size > MAX_LOCAL_BYTES) throw new Error("Локальный JSON превышает 50 МБ. Откройте отчёт по ID с сервера.");
      const text = await abortable(file.text(), operation.controller.signal);
      if (operationRef.current !== operation) return;
      let value: unknown;
      try { value = JSON.parse(text.replace(/^\uFEFF/, "")); }
      catch { throw new Error("Файл не является корректным JSON."); }
      const rep = asReport(value);
      if (!rep) throw new Error("JSON не соответствует формату Report. Выберите сохранённый отчёт, а не журнал событий.");
      setReport(rep);
      setRunId(rep.run_id);
      setLookupId(rep.run_id);
      setPhase("done");
      setTraceNote("Локальный Report открыт без отправки на сервер. JSON не содержит журнал действий; для журнала откройте этот ID на сервере.");
      rememberRun(null);
    } catch (err) {
      if (operationRef.current !== operation) return;
      setError(errorMessage(err, operation));
      setPhase("failed");
    } finally { finish(operation); }
  };

  const submit = async (): Promise<void> => {
    if (busy) return;
    if (!before.length || !after.length) {
      setError("Выберите хотя бы один файл до и после изменений.");
      return;
    }
    const requested = useLlm;
    const operation = begin("running", 300_000);
    setLlmRequested(requested);
    rememberRun(null);
    let acc = initialRunState;
    let terminal = false;
    const onEvent = (event: RunEvent): void => {
      if (operationRef.current !== operation || terminal || operation.controller.signal.aborted) return;
      if (acc.runId && event.run_id && acc.runId !== event.run_id) return;
      if (event.seq <= acc.lastSeq) return;
      acc = applyEvent(acc, event, { includeTokens: false });
      setRun(acc);
      if (acc.runId) {
        setRunId(acc.runId);
        setLookupId(acc.runId);
        rememberRun(acc.runId);
      }
      if (event.type === "final") {
        terminal = true;
        const rep = asReport(event.data.payload);
        if (!rep || (acc.runId && rep.run_id !== acc.runId)) {
          setError("Финальное событие не содержит корректный Report этого запуска.");
          setPhase("failed");
        } else {
          setReport(rep);
          setRunId(rep.run_id);
          setLookupId(rep.run_id);
          setPhase("done");
          rememberRun(rep.run_id);
        }
        // A terminal event is enough: do not wait forever for the server to close SSE.
        operation.controller.abort();
      } else if (event.type === "error" && event.data.recoverable !== true) {
        terminal = true;
        setError(`Сервер остановил аудит: ${event.data.message || "причина не указана"}`);
        setPhase("failed");
        operation.controller.abort();
      }
    };
    try {
      const response = await abortable(startAudit({ before, after, useLlm: requested, signal: operation.controller.signal }), operation.controller.signal);
      await abortable(readSseEvents(response, onEvent), operation.controller.signal);
      if (operationRef.current === operation && !terminal) {
        setPhase("failed");
        setError(acc.lastSeq < 0
          ? "Сервер закрыл пустой поток: событий аудита нет. Проверьте API и повторите запуск."
          : "Поток закрыт до получения Report. Аудит не подтверждён; попробуйте открыть результат по ID.");
      }
    } catch (err) {
      if (operationRef.current !== operation || terminal) return;
      setPhase("failed");
      setError(errorMessage(err, operation));
    } finally { finish(operation); }
  };

  return (
    <div className="mx-auto grid w-full max-w-[96rem] grid-cols-1 gap-5 p-4 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
      <aside className="space-y-5 lg:sticky lg:top-4 lg:max-h-[calc(100vh-5.5rem)] lg:self-start lg:overflow-y-auto">
        <div className="space-y-4 rounded-xl border border-neutral-800 bg-neutral-900 p-5 shadow-md shadow-black/20 lg:sticky lg:top-0 lg:z-10">
          <h2 className="flex items-center gap-2 text-sm font-medium text-neutral-100"><GitCompareArrows size={16} className="text-sky-400" /> Сравнить редакции</h2>
          <div className="space-y-3">
            <label className="flex cursor-pointer items-start gap-3 text-sm">
              <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} disabled={busy} className="mt-1 shrink-0 accent-violet-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500" />
              <span><span className="font-medium text-neutral-100">Запросить проверку ИИ-агентом</span><span className="mt-1 block text-xs leading-relaxed text-neutral-300">Включайте только для разрешённых к отправке данных.</span></span>
            </label>
            <button type="button" onClick={() => void submit()} disabled={busy || !before.length || !after.length} className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-sky-700 px-4 text-sm font-semibold text-white shadow-sm shadow-black/20 hover:bg-sky-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400 disabled:cursor-not-allowed disabled:bg-neutral-700 disabled:text-neutral-300 disabled:shadow-none"><Play size={16} /> Начать аудит</button>
            {busy && <button type="button" onClick={() => operationRef.current?.controller.abort()} className="flex min-h-10 w-full items-center justify-center gap-2 rounded-lg border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm text-red-200 hover:bg-neutral-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400"><CircleStop size={16} /> Остановить ожидание{running ? ` · ${(elapsedMs / 1000).toFixed(1)} с` : ""}</button>}
            <details className="text-xs leading-relaxed text-neutral-300">
              <summary className="w-fit cursor-pointer rounded hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500">Как работает проверка ИИ</summary>
              <p className="mt-2">Необязательно. Без модели работает алгоритмическое сравнение. Галочка не подтверждает выполнение агента — смотрите статус в отчёте.</p>
            </details>
          </div>
        </div>
        <div className="space-y-4 rounded-xl border border-neutral-800 bg-neutral-900/50 p-5">
          <AuditFilePicker label="До" hint="предыдущая редакция и приложения" files={before} onChange={setBefore} disabled={busy} />
          <AuditFilePicker label="После" hint="новая редакция и приложения" files={after} onChange={setAfter} disabled={busy} />
          <details className="text-xs leading-relaxed text-neutral-400">
            <summary className="w-fit cursor-pointer rounded text-neutral-300 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500">О времени ожидания и API</summary>
            <p className="mt-2">Ожидание аудита ограничено 5 минутами, открытие — 30 секундами. Это предел интерфейса, не доказательство полной проверки.</p>
            <div className="mt-2 break-all font-mono">POST {API_BASE}/audits</div>
          </details>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); if (!busy) void openReport(lookupId); }} className="space-y-3 rounded-xl border border-neutral-800 bg-neutral-900/50 p-5">
          <h2 className="flex items-center gap-2 text-sm font-medium text-neutral-100"><FolderOpen size={16} /> Открыть сохранённый аудит</h2>
          <label htmlFor="audit-run-id" className="block text-xs text-neutral-300">ID запуска на сервере</label>
          <div className="flex gap-2">
            <input id="audit-run-id" value={lookupId} onChange={(e) => setLookupId(e.target.value)} placeholder="run_id" disabled={busy} className="h-10 min-w-0 flex-1 rounded-lg border border-neutral-700 bg-neutral-900 px-3 font-mono text-sm text-neutral-100 outline-none focus:border-sky-500 disabled:opacity-60" />
            <button type="submit" disabled={busy || !lookupId.trim()} className="rounded-lg border border-neutral-700 bg-neutral-800/60 px-3 text-sm text-neutral-200 hover:bg-neutral-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500 disabled:cursor-not-allowed disabled:opacity-50">Открыть</button>
          </div>
          <p className="text-xs leading-relaxed text-neutral-400">Загружаются Report и фактический журнал событий сервера.</p>
          <button type="button" disabled={busy} onClick={() => localInputRef.current?.click()} className="min-h-10 w-full rounded-lg border border-neutral-700 bg-neutral-800/60 px-3 py-2 text-sm text-neutral-200 hover:bg-neutral-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500 disabled:cursor-not-allowed disabled:opacity-50">Загрузить локальный Report JSON</button>
          <input ref={localInputRef} type="file" accept=".json,application/json" disabled={busy} aria-label="Локальный Report JSON" className="hidden" onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file && !busy) void loadLocal(file); }} />
          <p className="text-xs leading-relaxed text-neutral-400">До 50 МБ. Локальный файл не отправляется на сервер.</p>
        </form>
        <div className="flex max-h-[32rem] flex-col rounded-xl border border-neutral-800 bg-neutral-900/50">
          <h2 className="flex items-center gap-2 border-b border-neutral-800 px-4 py-3 text-sm font-medium text-neutral-200"><ListTree size={16} /> Фактические действия <span className="ml-auto text-xs text-neutral-400">записей: {run.rows.length}</span></h2>
          <p className="px-4 pt-3 text-xs leading-relaxed text-neutral-400">Имена инструментов, аргументы, результаты и публичные основания. Скрытые рассуждения модели не выводятся. Системные шаги не доказывают участие агента.</p>
          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
            {traceNote && <p role="status" className="rounded-lg border border-neutral-700 bg-neutral-800/50 p-3 text-xs text-amber-200">{traceNote}</p>}
            {run.rows.length === 0 && !busy && <p className="py-4 text-center text-xs text-neutral-400">Событий для отображения нет.</p>}
            {run.rows.map((row) => row.kind === "tool" ? <ToolRowView key={row.id} row={row} active={running} /> : row.kind === "status" ? <StatusLine key={row.id} row={row} /> : row.kind === "error" ? <ErrorRowView key={row.id} row={row} /> : null)}
            {running && run.rows.length === 0 && <p className="flex items-center gap-2 py-2 text-xs text-neutral-300"><Loader2 size={12} className="animate-spin text-sky-400" /> Отправляем файлы и ждём первое событие…</p>}
            <div ref={timelineEndRef} />
          </div>
        </div>
      </aside>
      <section className="min-w-0 space-y-4" aria-label="Результат аудита">
        <div className="flex flex-wrap items-center gap-2 text-xs" role="status" aria-live="polite">
          <span className="flex items-center gap-1.5 rounded-full border border-neutral-700 bg-neutral-900 px-2.5 py-1 text-neutral-200">
            {busy && <Loader2 size={11} className="animate-spin text-sky-400" />}
            {running ? `Аудит выполняется · ${(elapsedMs / 1000).toFixed(1)} с` : phase === "loading" ? "Открываем сохранённый аудит…" : phase === "done" ? "Отчёт получен" : phase === "failed" ? "Операция не завершена" : "Готов к загрузке"}
          </span>
          {report && <span className="rounded-full border border-neutral-700 px-2.5 py-1 text-neutral-300">{report.mode === "deterministic" ? "Алгоритмическое сравнение" : "С участием модели"}</span>}
          {runId && <span className="break-all font-mono text-[11px] text-neutral-400">ID: {runId}</span>}
          {report && <button type="button" onClick={() => downloadReport(report)} className="flex items-center gap-1.5 rounded-md border border-sky-800 px-2.5 py-1.5 text-sky-300"><Download size={13} /> Скачать Report JSON</button>}
        </div>
        {error && <div role="alert" className="rounded-lg border border-red-800 bg-red-950/40 px-3 py-2 text-sm text-red-300">{error}</div>}
        {report ? <>
          <p className="text-xs leading-relaxed text-neutral-400">JSON сохраняет полный отчёт и источники, но не журнал. Автономный HTML создаётся штатным Python-экспортёром из этого JSON; браузер не подменяет его генерацию.</p>
          <AuditReportView key={report.run_id} report={report} llmRequested={llmRequested} />
        </> : !busy && <div className="rounded-xl border border-dashed border-neutral-800 px-6 py-14 text-center text-sm text-neutral-400">Добавьте положения и приложения в комплекты «До» и «После», затем начните аудит.<p className="mt-3 text-xs">Проверьте изменения подразделений, функции и межподразделенческие риски. Из заключения перейдите к подтверждающим пунктам. Выводы рекомендательные: решение принимает ответственный эксперт.</p></div>}
      </section>
    </div>
  );
}
