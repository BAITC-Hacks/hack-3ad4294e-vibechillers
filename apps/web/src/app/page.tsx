"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bot,
  CircleStop,
  ListTree,
  Loader2,
  MessagesSquare,
  Play,
  Send,
  Server,
  User,
} from "lucide-react";
import {
  API_BASE,
  createSseParser,
  extractErrorMessage,
  parseRunEvent,
  type RunEvent,
  type SseFrame,
} from "../lib/api";
import { applyEvent, initialRunState, type RunState } from "../lib/timeline";
import {
  CitationChip,
  ErrorRowView,
  StatusLine,
  ToolRowView,
} from "../components/Timeline";
import { UploadDropzone } from "../components/UploadDropzone";

type Phase = "idle" | "running" | "done" | "failed";

interface ChatTurn {
  role: "user" | "assistant";
  text: string;
}

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [run, setRun] = useState<RunState>(initialRunState);
  const [phase, setPhase] = useState<Phase>("idle");
  const [streamError, setStreamError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);

  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const timelineEndRef = useRef<HTMLDivElement>(null);

  const running = phase === "running";
  const streaming = running && run.streamed.length > 0 ? run.streamed : null;
  const answer = run.finalText !== null ? run.finalText : (streaming ?? "");

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, answer]);
  useEffect(() => {
    timelineEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, [run.rows.length]);
  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
    },
    []
  );

  const submit = useCallback(async (): Promise<void> => {
    const text = prompt.trim();
    if (text === "" || running) return;
    setPrompt("");
    setTurns((t) => [...t, { role: "user", text }]);
    setRun(initialRunState);
    setStreamError(null);
    setRunId(null);
    setPhase("running");
    setElapsedMs(0);
    const t0 = performance.now();
    timerRef.current = setInterval(
      () => setElapsedMs(performance.now() - t0),
      100
    );

    const controller = new AbortController();
    abortRef.current = controller;
    let acc = initialRunState;
    let sawTerminal = false;

    const onFrame = (frame: SseFrame): void => {
      const ev = parseRunEvent(frame);
      if (ev === null) return;
      if (ev.run_id !== "") setRunId((r) => r ?? ev.run_id);
      // A second `final` after completion is a replay artefact — drop it.
      if (ev.type === "final" && acc.finalText !== null) return;
      if (
        ev.type === "final" ||
        (ev.type === "error" && ev.data.recoverable !== true)
      ) {
        sawTerminal = true;
      }
      acc = applyEvent(acc, ev);
      setRun(acc);
      if (ev.type === "final") setPhase("done");
      if (ev.type === "error" && ev.data.recoverable !== true)
        setPhase("failed");
    };
    const parser = createSseParser(onFrame);

    try {
      const res = await fetch(`${API_BASE}/run`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ prompt: text, history: null }),
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(await extractErrorMessage(res));
      if (res.body === null) throw new Error("Response has no body to stream");
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        parser.feed(decoder.decode(value, { stream: true }));
      }
      parser.feed(decoder.decode());
      parser.end();
      if (!sawTerminal && acc.finalText === null && acc.errored === null) {
        setPhase("failed");
        setStreamError(
          "Stream ended before a final event arrived (run did not complete)"
        );
      }
    } catch (err) {
      if (controller.signal.aborted) {
        setPhase(acc.finalText !== null ? "done" : "idle");
        setStreamError("Run cancelled");
      } else {
        setPhase((p) => (p === "done" || p === "failed" ? p : "failed"));
        setStreamError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setElapsedMs(performance.now() - t0);
      abortRef.current = null;
    }
  }, [prompt, running]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  };

  const badge =
    phase === "running" ? (
      <span className="flex items-center gap-1.5 rounded-full border border-sky-800 bg-sky-950/40 px-2.5 py-0.5 text-xs text-sky-300">
        <Loader2 size={11} className="animate-spin" />
        running · {(elapsedMs / 1000).toFixed(1)}s
      </span>
    ) : phase === "done" ? (
      <span className="rounded-full border border-emerald-800 bg-emerald-950/40 px-2.5 py-0.5 text-xs text-emerald-300">
        run complete
      </span>
    ) : phase === "failed" ? (
      <span className="rounded-full border border-red-800 bg-red-950/40 px-2.5 py-0.5 text-xs text-red-300">
        run failed
      </span>
    ) : (
      <span className="rounded-full border border-neutral-800 bg-neutral-900 px-2.5 py-0.5 text-xs text-neutral-500">
        idle
      </span>
    );

  return (
    <main className="flex min-h-screen flex-col bg-neutral-950 text-neutral-100">
      <header className="flex items-center gap-3 border-b border-neutral-800/80 px-4 py-2.5">
        <div className="flex items-center gap-2 font-semibold tracking-tight">
          <Bot size={17} className="text-sky-400" />
          kit
        </div>
        <span className="hidden items-center gap-1 font-mono text-[11px] text-neutral-500 sm:flex">
          <Server size={10} className="text-neutral-600" />
          {API_BASE}
        </span>
        <div className="ml-auto flex items-center gap-2">
          {badge}
          {runId && (
            <span
              className="hidden max-w-44 truncate font-mono text-[11px] text-neutral-500 md:inline"
              title={runId}
            >
              {runId}
            </span>
          )}
        </div>
      </header>

      <div className="mx-auto grid w-full max-w-6xl flex-1 grid-cols-1 gap-4 p-4 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        {/* Chat column */}
        <section className="flex min-h-[60vh] flex-col rounded-xl border border-neutral-800 bg-neutral-900/40 lg:h-[calc(100vh-6.5rem)]">
          <div className="flex items-center gap-2 border-b border-neutral-800/80 px-3.5 py-2 text-xs font-medium uppercase tracking-wide text-neutral-400">
            <MessagesSquare size={12} className="text-neutral-600" />
            Chat
          </div>
          <div className="flex-1 space-y-4 overflow-y-auto p-3.5">
            {turns.length === 0 && !running && (
              <div className="mt-10 text-center text-sm text-neutral-500">
                Upload a document, then ask the agent about it.
                <br />
                <span className="text-neutral-600">
                  Enter submits · Shift+Enter adds a line
                </span>
              </div>
            )}
            {turns.map((t, i) => (
              <div key={i} className="flex gap-2.5">
                <div
                  className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
                    t.role === "user"
                      ? "bg-neutral-800 text-neutral-300"
                      : "bg-sky-950 text-sky-400"
                  }`}
                >
                  {t.role === "user" ? <User size={13} /> : <Bot size={13} />}
                </div>
                <div
                  className={`min-w-0 whitespace-pre-wrap break-words rounded-xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    t.role === "user"
                      ? "bg-neutral-800/90 text-neutral-100"
                      : "border border-neutral-800 bg-neutral-900 text-neutral-200"
                  }`}
                >
                  {t.text}
                </div>
              </div>
            ))}
            {(running || answer !== "") && phase !== "idle" && (
              <div className="flex gap-2.5">
                <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-sky-950 text-sky-400">
                  <Bot size={13} />
                </div>
                <div className="min-w-0 flex-1 whitespace-pre-wrap break-words rounded-xl border border-neutral-800 bg-neutral-900 px-3.5 py-2.5 text-sm leading-relaxed text-neutral-200">
                  {answer === "" ? (
                    <span className="flex items-center gap-2 text-neutral-500">
                      <Loader2 size={13} className="animate-spin" />
                      thinking…
                    </span>
                  ) : (
                    <>
                      {answer}
                      {running && (
                        <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-sky-400 align-text-bottom" />
                      )}
                    </>
                  )}
                  {phase === "done" && (
                    <div className="mt-2 border-t border-neutral-800 pt-1.5 text-[10px] uppercase tracking-wide text-emerald-500">
                      final · {(elapsedMs / 1000).toFixed(1)}s
                    </div>
                  )}
                </div>
              </div>
            )}
            {streamError && phase !== "running" && (
              <div className="ml-9 rounded-lg border border-red-800 bg-red-950/40 px-3 py-2 text-xs text-red-300">
                {streamError}
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <div className="border-t border-neutral-800/80 p-2.5">
            <div className="flex items-end gap-2">
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={onKeyDown}
                rows={Math.min(4, Math.max(1, prompt.split("\n").length))}
                placeholder="Ask about your documents…"
                disabled={running}
                className="max-h-40 min-h-10 flex-1 resize-none rounded-lg border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-sky-600 disabled:opacity-60"
              />
              {running ? (
                <button
                  type="button"
                  onClick={() => abortRef.current?.abort()}
                  className="flex h-10 items-center gap-1.5 rounded-lg border border-red-800 bg-red-950/40 px-3 text-sm text-red-300 hover:bg-red-950/70"
                >
                  <CircleStop size={15} />
                  Stop
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => void submit()}
                  disabled={prompt.trim() === ""}
                  className="flex h-10 items-center gap-1.5 rounded-lg bg-sky-600 px-3.5 text-sm font-medium text-white hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500"
                >
                  <Send size={14} />
                  Run
                </button>
              )}
            </div>
          </div>
        </section>

        {/* Right rail: upload + trace */}
        <section className="flex min-h-[40vh] flex-col gap-4 lg:h-[calc(100vh-6.5rem)]">
          <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
            <div className="mb-2 text-xs font-medium uppercase tracking-wide text-neutral-400">
              Upload
            </div>
            <UploadDropzone />
          </div>

          <div className="flex min-h-0 flex-1 flex-col rounded-xl border border-neutral-800 bg-neutral-900/40">
            <div className="flex items-center gap-2 border-b border-neutral-800/80 px-3.5 py-2 text-xs font-medium uppercase tracking-wide text-neutral-400">
              <ListTree size={12} className="text-neutral-600" />
              Run trace
              <span className="ml-auto normal-case tracking-normal text-neutral-600">
                {run.rows.length} events
                {run.droppedStale > 0 &&
                  ` · ${run.droppedStale} stale dropped`}
              </span>
            </div>
            <div className="flex-1 space-y-2 overflow-y-auto p-2.5">
              {run.rows.length === 0 && !running && (
                <div className="mt-8 text-center text-xs text-neutral-600">
                  Tool calls, statuses, citations and errors for the current
                  run appear here.
                </div>
              )}
              {run.rows.map((r) =>
                r.kind === "tool" ? (
                  <ToolRowView key={r.id} row={r} />
                ) : r.kind === "status" ? (
                  <StatusLine key={r.id} row={r} />
                ) : r.kind === "citation" ? (
                  <CitationChip key={r.id} row={r} />
                ) : (
                  <ErrorRowView key={r.id} row={r} />
                )
              )}
              {running && run.rows.length === 0 && (
                <div className="flex items-center gap-2 px-1 py-2 text-xs text-neutral-500">
                  <Play size={11} className="animate-pulse text-sky-400" />
                  awaiting first event…
                </div>
              )}
              <div ref={timelineEndRef} />
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
