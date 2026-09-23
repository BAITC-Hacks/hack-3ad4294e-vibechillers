import type { RunEvent } from "./api";

export interface ToolRow {
  kind: "tool";
  id: string;
  seq: number;
  ts: number;
  callId: string;
  name: string;
  args: Record<string, unknown>;
  done: boolean;
  ok: boolean | null;
  result: unknown;
  ms: number | null;
  reason?: string;
}

export interface StatusRow {
  kind: "status";
  id: string;
  seq: number;
  ts: number;
  message: string;
}

export interface CitationRow {
  kind: "citation";
  id: string;
  seq: number;
  ts: number;
  docId: string;
  source: string;
  page: number | null;
  snippet: string;
}

export interface ErrorRow {
  kind: "error";
  id: string;
  seq: number;
  ts: number;
  message: string;
  recoverable: boolean;
}

export type TimelineRow =
  | ToolRow
  | StatusRow
  | CitationRow
  | ErrorRow;

export interface RunState {
  rows: TimelineRow[];
  streamed: string;
  finalText: string | null;
  errored: string | null;
  runId: string;
  lastSeq: number;
  droppedStale: number;
}

export const initialRunState: RunState = {
  rows: [],
  streamed: "",
  finalText: null,
  errored: null,
  runId: "",
  lastSeq: -1,
  droppedStale: 0,
};

/**
 * Fold one SSE event into the run state. Ordering is trusted from `seq`:
 * events at or below the highest seen seq are dropped as stale (a duplicate
 * replay or an out-of-order tail), and token deltas never become timeline
 * rows — they append to `streamed` unless disabled by the audit consumer.
 */
export function applyEvent(
  state: RunState,
  ev: RunEvent,
  { includeTokens = true }: { includeTokens?: boolean } = {}
): RunState {
  if (state.runId && ev.run_id && state.runId !== ev.run_id) return state;
  if (Number.isFinite(ev.seq) && ev.seq <= state.lastSeq) {
    return { ...state, droppedStale: state.droppedStale + 1 };
  }
  const base: RunState = {
    ...state,
    lastSeq: Number.isFinite(ev.seq) ? ev.seq : state.lastSeq,
    runId: ev.run_id || state.runId,
  };
  const id = `${ev.type}-${base.lastSeq}-${base.rows.length}`;

  switch (ev.type) {
    case "token":
      return includeTokens
        ? { ...base, streamed: base.streamed + String(ev.data.text ?? "") }
        : base;

    case "status":
      return {
        ...base,
        rows: [
          ...base.rows,
          {
            kind: "status",
            id,
            seq: ev.seq,
            ts: ev.ts,
            message: String(ev.data.message ?? ""),
          },
        ],
      };

    case "tool_call":
      return {
        ...base,
        rows: [
          ...base.rows,
          {
            kind: "tool",
            id,
            seq: ev.seq,
            ts: ev.ts,
            callId: String(ev.data.call_id ?? ""),
            name: String(ev.data.name ?? "?"),
            args:
              typeof ev.data.args === "object" && ev.data.args !== null
                ? (ev.data.args as Record<string, unknown>)
                : {},
            reason: publicReason(ev.data.args),
            done: false,
            ok: null,
            result: null,
            ms: null,
          },
        ],
      };

    case "tool_result": {
      const callId = String(ev.data.call_id ?? "");
      const idx = base.rows.findIndex(
        (r) => r.kind === "tool" && !r.done && r.callId === callId
      );
      const row: ToolRow = {
        kind: "tool",
        id: idx === -1 ? id : base.rows[idx].id,
        seq: ev.seq,
        ts: ev.ts,
        callId,
        name: String(ev.data.name ?? (idx === -1 ? "?" : (base.rows[idx] as ToolRow).name)),
        args: idx === -1 ? {} : (base.rows[idx] as ToolRow).args,
        done: true,
        ok: typeof ev.data.ok === "boolean" ? ev.data.ok : null,
        result: ev.data.result ?? null,
        ms: typeof ev.data.ms === "number" ? ev.data.ms : null,
        reason: publicReason(ev.data.result) ||
          (idx === -1 ? undefined : (base.rows[idx] as ToolRow).reason),
      };
      const rows =
        idx === -1
          ? [...base.rows, row]
          : base.rows.map((r, i) => (i === idx ? row : r));
      return { ...base, rows };
    }

    case "citation":
      return {
        ...base,
        rows: [
          ...base.rows,
          {
            kind: "citation",
            id,
            seq: ev.seq,
            ts: ev.ts,
            docId: String(ev.data.doc_id ?? ""),
            source: String(ev.data.source ?? ""),
            page: typeof ev.data.page === "number" ? ev.data.page : null,
            snippet: String(ev.data.snippet ?? ""),
          },
        ],
      };

    case "error":
      return {
        ...base,
        errored: String(ev.data.message ?? "unknown error"),
        rows: [
          ...base.rows,
          {
            kind: "error",
            id,
            seq: ev.seq,
            ts: ev.ts,
            message: String(ev.data.message ?? "unknown error"),
            recoverable: ev.data.recoverable === true,
          },
        ],
      };

    case "final":
      return {
        ...base,
        finalText: String(ev.data.text ?? base.streamed),
      };
  }
}

/** Only explicit, public evidence summaries; token/model reasoning is never a reason. */
function publicReason(value: unknown): string | undefined {
  if (!value || typeof value !== "object") return undefined;
  const reason = (value as Record<string, unknown>).reason;
  return typeof reason === "string" ? reason.slice(0, 600) : undefined;
}
