"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  CircleStop,
  FolderOpen,
  GitCompareArrows,
  ListTree,
  Loader2,
  Play,
} from "lucide-react";
import {
  API_BASE,
  asReport,
  fetchAuditReport,
  readSseEvents,
  startAudit,
  type Report,
  type RunEvent,
} from "../lib/api";
import { applyEvent, initialRunState, type RunState } from "../lib/timeline";
import { ErrorRowView, StatusLine, ToolRowView } from "./Timeline";
import { AuditFilePicker } from "./UploadDropzone";
import { AuditReportView } from "./AuditReport";

type Phase = "idle" | "running" | "done" | "failed";

/** Keeps `?run=<id>` in the address bar so a finished audit can be reopened via GET /audits/{run_id}. */
function rememberRun(runId: string): void {
  const url = new URL(window.location.href);
  url.searchParams.set("run", runId);
  window.history.replaceState(null, "", url);
}

export function AuditWorkspace() {
  const [before, setBefore] = useState<File[]>([]);
  const [after, setAfter] = useState<File[]>([]);
  const [useLlm, setUseLlm] = useState(false);
  const [run, setRun] = useState<RunState>(initialRunState);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [llmRequested, setLlmRequested] = useState<boolean | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [lookupId, setLookupId] = useState("");
  const [loadingReport, setLoadingReport] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<number | null>(null);
  const timelineEndRef = useRef<HTMLDivElement>(null);

  const running = phase === "running";

  useEffect(() => {
    timelineEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [run.rows.length]);
  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
      abortRef.current?.abort();
    },
    []
  );

  const openReport = useCallback(async (id: string): Promise<void> => {
    const target = id.trim();
    if (target === "") return;
    setLoadingReport(true);
    setError(null);
    try {
      const rep = await fetchAuditReport(target);
      setRun(initialRunState);
      setReport(rep);
      setRunId(rep.run_id);
      setLlmRequested(null);
      setPhase("done");
      rememberRun(rep.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingReport(false);
    }
  }, []);

  useEffect(() => {
    const id = new URL(window.location.href).searchParams.get("run");
    if (id) {
      setLookupId(id);
      void openReport(id);
    }
  }, [openReport]);

  const submit = async (): Promise<void> => {
    if (running) return;
    if (before.length === 0 || after.length === 0) {
      setError("Select at least one file for each side (before and after).");
      return;
    }
    const requested = useLlm;
    setRun(initialRunState);
    setReport(null);
    setError(null);
    setRunId(null);
    setLlmRequested(requested);
    setPhase("running");
    setElapsedMs(0);
    const t0 = performance.now();
    timerRef.current = window.setInterval(() => setElapsedMs(performance.now() - t0), 100);

    const controller = new AbortController();
    abortRef.current = controller;
    let acc = initialRunState;
    let finished = false;

    const onEvent = (ev: RunEvent): void => {
      if (ev.run_id !== "") setRunId((r) => r ?? ev.run_id);
      // A second `final` after completion is a replay artefact — drop it.
      if (ev.type === "final" && acc.finalText !== null) return;
      acc = applyEvent(acc, ev);
      setRun(acc);
      if (ev.type === "final") {
        finished = true;
        const rep = asReport(ev.data.payload);
        if (rep === null) {
          setPhase("failed");
          setError("The final event did not carry a valid Report payload.");
          return;
        }
        setReport(rep);
        setPhase("done");
        rememberRun(rep.run_id);
      } else if (ev.type === "error" && ev.data.recoverable !== true) {
        finished = true;
        setPhase("failed");
      }
    };

    try {
      const res = await startAudit({
        before,
        after,
        useLlm: requested,
        signal: controller.signal,
      });
      await readSseEvents(res, onEvent);
      if (!finished) {
        setPhase("failed");
        setError("Stream ended before a final event arrived (audit did not complete).");
      }
    } catch (err) {
      if (controller.signal.aborted) {
        setPhase(acc.finalText !== null ? "done" : "idle");
        setError("Audit cancelled");
      } else {
        setPhase((p) => (p === "done" || p === "failed" ? p : "failed"));
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setElapsedMs(performance.now() - t0);
      abortRef.current = null;
    }
  };

  const lastStatus = [...run.rows].reverse().find((r) => r.kind === "status");

  return (
    <div className="mx-auto grid w-full max-w-[96rem] grid-cols-1 gap-4 p-4 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
      <aside className="space-y-4 lg:sticky lg:top-4 lg:max-h-[calc(100vh-5.5rem)] lg:self-start lg:overflow-y-auto">
        <div className="space-y-3 rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-neutral-400">
            <GitCompareArrows size={13} className="text-sky-400" />
            New audit
          </div>
          <AuditFilePicker
            label="Before"
            hint="previous edition(s)"
            files={before}
            onChange={setBefore}
            disabled={running}
          />
          <AuditFilePicker
            label="After"
            hint="new edition(s)"
            files={after}
            onChange={setAfter}
            disabled={running}
          />
          <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-neutral-800 bg-neutral-900/60 px-2.5 py-2 text-xs">
            <input
              type="checkbox"
              checked={useLlm}
              onChange={(e) => setUseLlm(e.target.checked)}
              disabled={running}
              className="mt-0.5 accent-violet-500"
            />
            <span>
              <span className="text-neutral-200">LLM adjudication</span>
              <span className="block text-[11px] text-neutral-500">
                Optional. Off gives a deterministic report; if the model is
                unavailable the audit still completes deterministically.
              </span>
            </span>
          </label>
          {running ? (
            <button
              type="button"
              onClick={() => abortRef.current?.abort()}
              className="flex h-9 w-full items-center justify-center gap-1.5 rounded-lg border border-red-800 bg-red-950/40 text-sm text-red-300 hover:bg-red-950/70"
            >
              <CircleStop size={15} />
              Stop · {(elapsedMs / 1000).toFixed(1)}s
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void submit()}
              disabled={before.length === 0 || after.length === 0}
              className="flex h-9 w-full items-center justify-center gap-1.5 rounded-lg bg-sky-600 text-sm font-medium text-white hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500"
            >
              <Play size={14} />
              Run audit
            </button>
          )}
          <div className="text-center font-mono text-[10px] text-neutral-600">
            POST {API_BASE}/audits
          </div>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void openReport(lookupId);
          }}
          className="space-y-2 rounded-xl border border-neutral-800 bg-neutral-900/40 p-3"
        >
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-neutral-400">
            <FolderOpen size={13} className="text-neutral-500" />
            Open saved audit
          </div>
          <div className="flex gap-2">
            <input
              value={lookupId}
              onChange={(e) => setLookupId(e.target.value)}
              placeholder="run_id"
              className="min-w-0 flex-1 rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 font-mono text-xs text-neutral-100 placeholder-neutral-600 outline-none focus:border-sky-600"
            />
            <button
              type="submit"
              disabled={running || loadingReport || lookupId.trim() === ""}
              className="flex items-center gap-1 rounded-md border border-neutral-700 px-2.5 text-xs text-neutral-300 hover:border-neutral-500 disabled:opacity-50"
            >
              {loadingReport && <Loader2 size={12} className="animate-spin" />}
              Open
            </button>
          </div>
        </form>

        <div className="flex max-h-96 flex-col rounded-xl border border-neutral-800 bg-neutral-900/40">
          <div className="flex items-center gap-2 border-b border-neutral-800/80 px-3 py-2 text-xs font-medium uppercase tracking-wide text-neutral-400">
            <ListTree size={12} className="text-neutral-600" />
            Progress
            <span className="ml-auto normal-case tracking-normal text-neutral-600">
              {run.rows.length} events
            </span>
          </div>
          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-2.5">
            {run.rows.length === 0 && !running && (
              <div className="py-4 text-center text-xs text-neutral-600">
                Ingestion, parsing, alignment and report events appear here.
              </div>
            )}
            {run.rows.map((r) =>
              r.kind === "tool" ? (
                <ToolRowView key={r.id} row={r} />
              ) : r.kind === "status" ? (
                <StatusLine key={r.id} row={r} />
              ) : r.kind === "error" ? (
                <ErrorRowView key={r.id} row={r} />
              ) : null
            )}
            {running && run.rows.length === 0 && (
              <div className="flex items-center gap-2 px-1 py-2 text-xs text-neutral-500">
                <Loader2 size={11} className="animate-spin text-sky-400" />
                uploading and awaiting first event…
              </div>
            )}
            <div ref={timelineEndRef} />
          </div>
        </div>
      </aside>

      <section className="min-w-0 space-y-4">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {phase === "running" ? (
            <span className="flex items-center gap-1.5 rounded-full border border-sky-800 bg-sky-950/40 px-2.5 py-0.5 text-sky-300">
              <Loader2 size={11} className="animate-spin" />
              auditing · {(elapsedMs / 1000).toFixed(1)}s
            </span>
          ) : phase === "done" ? (
            <span className="rounded-full border border-emerald-800 bg-emerald-950/40 px-2.5 py-0.5 text-emerald-300">
              audit complete
            </span>
          ) : phase === "failed" ? (
            <span className="rounded-full border border-red-800 bg-red-950/40 px-2.5 py-0.5 text-red-300">
              audit failed
            </span>
          ) : (
            <span className="rounded-full border border-neutral-800 bg-neutral-900 px-2.5 py-0.5 text-neutral-500">
              idle
            </span>
          )}
          {report && (
            <span
              className={`rounded-full border px-2.5 py-0.5 ${
                report.mode === "deterministic"
                  ? "border-neutral-700 bg-neutral-900 text-neutral-300"
                  : "border-violet-800 bg-violet-950/40 text-violet-300"
              }`}
            >
              mode: {report.mode}
            </span>
          )}
          {runId && (
            <span className="truncate font-mono text-[11px] text-neutral-500" title={runId}>
              {runId}
            </span>
          )}
          {running && lastStatus?.kind === "status" && (
            <span className="min-w-0 truncate text-neutral-500">{lastStatus.message}</span>
          )}
        </div>

        {error && (
          <div className="rounded-lg border border-red-800 bg-red-950/40 px-3 py-2 text-xs text-red-300">
            {error}
          </div>
        )}
        {run.errored && phase === "failed" && run.errored !== error && (
          <div className="rounded-lg border border-red-800 bg-red-950/40 px-3 py-2 text-xs text-red-300">
            {run.errored}
          </div>
        )}

        {report ? (
          <AuditReportView key={report.run_id} report={report} llmRequested={llmRequested} />
        ) : (
          !running && (
            <div className="rounded-xl border border-dashed border-neutral-800 px-6 py-16 text-center text-sm text-neutral-500">
              Select the previous edition(s) as <span className="text-neutral-300">Before</span> and
              the new edition(s) as <span className="text-neutral-300">After</span>, then run the
              audit.
              <br />
              <span className="text-xs text-neutral-600">
                Every function clause is accounted for; each finding cites the exact preserved
                clause text.
              </span>
            </div>
          )
        )}
      </section>
    </div>
  );
}
