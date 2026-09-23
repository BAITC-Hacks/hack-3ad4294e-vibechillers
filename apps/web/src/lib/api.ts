/** Wire types shared with apps/api/app/events.py — the SSE envelope is the only contract. */

export const API_BASE: string =
  process.env.NEXT_PUBLIC_API_BASE?.trim() || "http://localhost:8000";

export type RunEventType =
  | "status"
  | "token"
  | "tool_call"
  | "tool_result"
  | "citation"
  | "final"
  | "error";

export interface StatusData {
  message: string;
}
export interface TokenData {
  text: string;
}
export interface ToolCallData {
  name: string;
  args: Record<string, unknown>;
  call_id: string;
}
export interface ToolResultData {
  name: string;
  call_id: string;
  ok: boolean;
  result: unknown;
  ms: number;
}
export interface CitationData {
  doc_id: string;
  source: string;
  page: number | null;
  snippet: string;
}
export interface FinalData {
  text: string;
  payload: unknown;
}
export interface ErrorData {
  message: string;
  recoverable: boolean;
}

export interface RunEvent {
  type: RunEventType;
  run_id: string;
  seq: number;
  ts: number;
  data: Partial<
    StatusData &
      TokenData &
      ToolCallData &
      ToolResultData &
      CitationData &
      FinalData &
      ErrorData
  >;
}

export interface UploadOk {
  doc_id: string;
  chunks: number;
  pages: number;
}

/**
 * Incremental SSE frame parser for `event: <type>\ndata: <json>\n\n` streams.
 * `feed` accepts arbitrary chunk boundaries (frames and even header lines may
 * split across reads); each completed frame is passed to `onFrame`.
 * `end` flushes a trailing frame that wasn't followed by a blank line.
 */
export interface SseFrame {
  event: string;
  data: string;
}

export function createSseParser(onFrame: (frame: SseFrame) => void): {
  feed: (text: string) => void;
  end: () => void;
} {
  let buf = "";

  const consumeBlock = (block: string): void => {
    let data = "";
    let sawData = false;
    let eventName = "";
    for (const rawLine of block.split("\n")) {
      const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
      if (line === "" || line.startsWith(":")) continue;
      const colon = line.indexOf(":");
      const field = colon === -1 ? line : line.slice(0, colon);
      let value = colon === -1 ? "" : line.slice(colon + 1);
      if (value.startsWith(" ")) value = value.slice(1);
      if (field === "event") eventName = value;
      else if (field === "data") {
        data = sawData ? `${data}\n${value}` : value;
        sawData = true;
      }
    }
    if (sawData) onFrame({ event: eventName, data });
  };

  return {
    feed(text: string): void {
      buf += text;
      for (;;) {
        const nl = buf.indexOf("\n\n");
        const crlf = buf.indexOf("\r\n\r\n");
        let cut = -1;
        let sep = 0;
        if (nl !== -1 && (crlf === -1 || nl < crlf)) {
          cut = nl;
          sep = 2;
        } else if (crlf !== -1) {
          cut = crlf;
          sep = 4;
        }
        if (cut === -1) break;
        const block = buf.slice(0, cut);
        buf = buf.slice(cut + sep);
        consumeBlock(block);
      }
    },
    end(): void {
      if (buf !== "") {
        const block = buf;
        buf = "";
        consumeBlock(block);
      }
    },
  };
}

/** Parse one frame's JSON body; tolerates a missing/!valid `type` by falling back to the SSE event name. */
export function parseRunEvent(frame: SseFrame): RunEvent | null {
  let obj: unknown;
  try {
    obj = JSON.parse(frame.data);
  } catch {
    return null;
  }
  if (typeof obj !== "object" || obj === null) return null;
  const rec = obj as Record<string, unknown>;
  const type =
    typeof rec.type === "string" ? rec.type : frame.event;
  if (!isRunEventType(type)) return null;
  return {
    type,
    run_id: typeof rec.run_id === "string" ? rec.run_id : "",
    seq: typeof rec.seq === "number" ? rec.seq : Number.NaN,
    ts: typeof rec.ts === "number" ? rec.ts : 0,
    data:
      typeof rec.data === "object" && rec.data !== null
        ? (rec.data as RunEvent["data"])
        : {},
  };
}

function isRunEventType(v: string): v is RunEventType {
  return (
    v === "status" ||
    v === "token" ||
    v === "tool_call" ||
    v === "tool_result" ||
    v === "citation" ||
    v === "final" ||
    v === "error"
  );
}

/** Pull a human-readable message out of any error body shape (contract envelope, FastAPI detail, bare string). */
export async function extractErrorMessage(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  if (!text) return `HTTP ${res.status}`;
  try {
    const j: unknown = JSON.parse(text);
    if (typeof j === "object" && j !== null) {
      const rec = j as Record<string, unknown>;
      const err = rec.error;
      if (typeof err === "string") return err;
      if (typeof err === "object" && err !== null) {
        const m = (err as Record<string, unknown>).message;
        if (typeof m === "string") return m;
      }
      if (typeof rec.detail === "string") return rec.detail;
      if (typeof rec.detail === "object" && rec.detail !== null) {
        const d0 = (rec.detail as Record<string, unknown>).message ?? (rec.detail as unknown[])[0];
        if (typeof d0 === "string") return d0;
        if (typeof d0 === "object" && d0 !== null) {
          const msg = (d0 as Record<string, unknown>).msg;
          if (typeof msg === "string") return msg;
        }
      }
      if (typeof rec.message === "string") return rec.message;
    }
  } catch {
    /* not JSON */
  }
  return text.length > 300 ? `${text.slice(0, 300)}…` : text;
}

/**
 * Read an SSE response body to completion, handing every well-formed kit
 * `Event` frame to `onEvent`. Shared by `/run` and `/audits`: one parser, one
 * envelope.
 */
export async function readSseEvents(
  res: Response,
  onEvent: (ev: RunEvent) => void
): Promise<void> {
  if (res.body === null) throw new Error("Response has no body to stream");
  const parser = createSseParser((frame) => {
    const ev = parseRunEvent(frame);
    if (ev !== null) onEvent(ev);
  });
  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parser.feed(decoder.decode(value, { stream: true }));
  }
  parser.feed(decoder.decode());
  parser.end();
}

/* ---------------------------------------------------------------------------
 * Function Lineage Auditor wire types — docs/plan.md §3 "Data", verbatim.
 * ------------------------------------------------------------------------- */

export type Edition = "before" | "after";
export type ClauseKind = "heading" | "function" | "structure" | "other";
export type UnitKind = "unit" | "role";
export type FindingStatus =
  | "unchanged"
  | "changed"
  | "moved"
  | "added"
  | "missing"
  | "duplicate"
  | "unresolved";
export type FindingMethod = "exact" | "lexical" | "llm" | "human";
export type ReportMode = "deterministic" | "llm_assisted";

export interface AuditDocument {
  doc: string;
  doc_id: string;
  sha256: string;
  edition: Edition;
  source: string;
}
export interface Citation {
  doc: string;
  clause_id: string;
  quote: string;
}
export interface ClauseRef {
  doc: string;
  clause_id: string;
}
export interface Clause {
  doc: string;
  clause_id: string;
  label: string;
  parent_id: string | null;
  text: string;
  ordinal: number;
  kind: ClauseKind;
  unit_ids: string[];
}
export interface Unit {
  doc: string;
  unit_id: string;
  name: string;
  kind: UnitKind;
  parent_unit_id: string | null;
  citations: Citation[];
}
export interface Finding {
  id: string;
  status: FindingStatus;
  before: ClauseRef[];
  after: ClauseRef[];
  citations: Citation[];
  reason: string;
  method: FindingMethod;
  review_required: boolean;
}
export interface ConclusionItem {
  text: string;
  finding_ids: string[];
  citations: Citation[];
}
export interface Coverage {
  before_total: number;
  after_total: number;
  before_accounted: number;
  after_accounted: number;
  unresolved: number;
}
export interface Report {
  run_id: string;
  mode: ReportMode;
  documents: AuditDocument[];
  clauses: Clause[];
  units: Unit[];
  findings: Finding[];
  conclusion: ConclusionItem[];
  coverage: Coverage;
  warnings: string[];
}

/**
 * Structural gate on an untrusted `final.data.payload` / GET body. Returns
 * null rather than coercing: a malformed report must surface as an error,
 * never render as an empty-but-successful audit.
 */
export function asReport(v: unknown): Report | null {
  if (typeof v !== "object" || v === null) return null;
  const r = v as Record<string, unknown>;
  if (typeof r.run_id !== "string") return null;
  if (r.mode !== "deterministic" && r.mode !== "llm_assisted") return null;
  for (const key of [
    "documents",
    "clauses",
    "units",
    "findings",
    "conclusion",
    "warnings",
  ]) {
    if (!Array.isArray(r[key])) return null;
  }
  const cov = r.coverage;
  if (typeof cov !== "object" || cov === null) return null;
  const c = cov as Record<string, unknown>;
  for (const key of [
    "before_total",
    "after_total",
    "before_accounted",
    "after_accounted",
    "unresolved",
  ]) {
    if (typeof c[key] !== "number") return null;
  }
  return v as Report;
}

/** `POST /audits` — multipart repeated `before_files` / `after_files`, `use_llm`. Returns the raw SSE response. */
export async function startAudit(opts: {
  before: File[];
  after: File[];
  useLlm: boolean;
  signal?: AbortSignal;
}): Promise<Response> {
  const form = new FormData();
  for (const f of opts.before) form.append("before_files", f, f.name);
  for (const f of opts.after) form.append("after_files", f, f.name);
  form.append("use_llm", opts.useLlm ? "true" : "false");
  const res = await fetch(`${API_BASE}/audits`, {
    method: "POST",
    body: form,
    signal: opts.signal,
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${await extractErrorMessage(res)}`);
  }
  return res;
}

/** `GET /audits/{run_id}` — the persisted final Report (404 absent, 409 incomplete). */
export async function fetchAuditReport(
  runId: string,
  signal?: AbortSignal
): Promise<Report> {
  const res = await fetch(`${API_BASE}/audits/${encodeURIComponent(runId)}`, {
    signal,
  });
  if (!res.ok) {
    const msg = await extractErrorMessage(res);
    if (res.status === 404)
      throw new Error(`No audit report for run ${runId} (404): ${msg}`);
    if (res.status === 409)
      throw new Error(`Audit ${runId} has not completed yet (409): ${msg}`);
    throw new Error(`HTTP ${res.status}: ${msg}`);
  }
  const report = asReport(await res.json());
  if (report === null) {
    throw new Error(`GET /audits/${runId} returned a body that is not a Report`);
  }
  return report;
}
