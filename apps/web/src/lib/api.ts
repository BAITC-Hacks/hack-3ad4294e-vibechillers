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
export interface SourceLocation {
  page: number | null;
  block: number | null;
  sheet: string | null;
  cell_range: string | null;
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
  location?: SourceLocation | null;
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
export interface UnitRef {
  doc: string;
  unit_id: string;
}
export interface UnitChange {
  id: string;
  status: "retained" | "reorganised" | "created" | "unresolved";
  before: UnitRef[];
  after: UnitRef[];
  citations: Citation[];
  reason: string;
  method: FindingMethod;
  review_required: boolean;
}
export interface Risk {
  id: string;
  kind: "potential_duplication" | "potential_conflict_of_interest";
  units: UnitRef[];
  refs: ClauseRef[];
  citations: Citation[];
  reason: string;
  method: FindingMethod;
  review_required: true;
}
export interface AgentExecution {
  status: "not_requested" | "completed" | "partial" | "unavailable" | "failed";
  model: string | null;
  turns: number;
  tool_calls: number;
  investigated_finding_ids: string[];
  stop_reason: string;
}
export interface ConclusionItem {
  text: string;
  finding_ids: string[];
  citations: Citation[];
  unit_change_ids?: string[];
  risk_ids?: string[];
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
  /** Missing Stage 3 fields in historical reports mean "not assessed". */
  unit_changes?: UnitChange[];
  risks?: Risk[];
  agent?: AgentExecution | null;
}

/**
 * Structural gate on an untrusted `final.data.payload` / GET body. Returns
 * null rather than coercing: a malformed report must surface as an error,
 * never render as an empty-but-successful audit.
 */
export function asReport(v: unknown): Report | null {
  if (!record(v)) return null;
  if (typeof v.run_id !== "string" || !oneOf(v.mode, ["deterministic", "llm_assisted"])) return null;
  if (!rows(v.documents, (d) => strings(d, ["doc", "doc_id", "sha256", "source"]) &&
    oneOf(d.edition, ["before", "after"]))) return null;
  if (!rows(v.clauses, (c) => strings(c, ["doc", "clause_id", "label", "text"]) &&
    nullableString(c.parent_id) && nonnegative(c.ordinal) && stringList(c.unit_ids) &&
    oneOf(c.kind, ["heading", "function", "structure", "other"]) &&
    (c.location === undefined || c.location === null || validLocation(c.location)))) return null;
  if (!rows(v.units, (u) => strings(u, ["doc", "unit_id", "name"]) &&
    nullableString(u.parent_unit_id) && oneOf(u.kind, ["unit", "role"]) &&
    rows(u.citations, citation))) return null;
  if (!rows(v.findings, (f) => output(f) &&
    oneOf(f.status, ["unchanged", "changed", "moved", "added", "missing", "duplicate", "unresolved"]) &&
    rows(f.before, clauseRef) && rows(f.after, clauseRef))) return null;
  if (!rows(v.conclusion, (c) => typeof c.text === "string" && stringList(c.finding_ids) &&
    rows(c.citations, citation) && (c.unit_change_ids === undefined || stringList(c.unit_change_ids)) &&
    (c.risk_ids === undefined || stringList(c.risk_ids)))) return null;
  if (!stringList(v.warnings) || !record(v.coverage)) return null;
  if (!["before_total", "after_total", "before_accounted", "after_accounted", "unresolved"]
    .every((key) => nonnegative(v.coverage && (v.coverage as Record<string, unknown>)[key]))) return null;
  if (v.unit_changes !== undefined && !rows(v.unit_changes, (u) => output(u) &&
    oneOf(u.status, ["retained", "reorganised", "created", "unresolved"]) &&
    rows(u.before, unitRef) && rows(u.after, unitRef))) return null;
  if (v.risks !== undefined && !rows(v.risks, (r) => output(r) && r.review_required === true &&
    oneOf(r.kind, ["potential_duplication", "potential_conflict_of_interest"]) &&
    rows(r.units, unitRef) && rows(r.refs, clauseRef))) return null;
  if (v.agent !== undefined && v.agent !== null) {
    const a = v.agent;
    if (!record(a) || !oneOf(a.status, ["not_requested", "completed", "partial", "unavailable", "failed"]) ||
      !nullableString(a.model) || !nonnegative(a.turns) || !nonnegative(a.tool_calls) ||
      !stringList(a.investigated_finding_ids) || typeof a.stop_reason !== "string") return null;
  }
  for (const [items, keys] of [
    [v.documents, ["doc"]], [v.clauses, ["doc", "clause_id"]], [v.units, ["doc", "unit_id"]],
    [v.findings, ["id"]], [v.unit_changes ?? [], ["id"]], [v.risks ?? [], ["id"]],
  ] as [Record<string, unknown>[], string[]][]) {
    const seen = new Set<string>();
    for (const row of items) {
      const key = JSON.stringify(keys.map((field) => row[field]));
      if (seen.has(key)) return null;
      seen.add(key);
    }
  }
  return v as unknown as Report;
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function strings(row: Record<string, unknown>, keys: string[]): boolean {
  return keys.every((key) => typeof row[key] === "string");
}
function stringList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((v) => typeof v === "string");
}
function nullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}
function nonnegative(value: unknown): boolean {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}
function oneOf(value: unknown, allowed: readonly string[]): boolean {
  return typeof value === "string" && allowed.includes(value);
}
function rows(value: unknown, check: (row: Record<string, unknown>) => boolean): boolean {
  return Array.isArray(value) && value.every((row) => record(row) && check(row));
}
function clauseRef(row: Record<string, unknown>): boolean {
  return strings(row, ["doc", "clause_id"]);
}
function unitRef(row: Record<string, unknown>): boolean {
  return strings(row, ["doc", "unit_id"]);
}
function citation(row: Record<string, unknown>): boolean {
  return clauseRef(row) && typeof row.quote === "string";
}
function output(row: Record<string, unknown>): boolean {
  return strings(row, ["id", "reason"]) && typeof row.review_required === "boolean" &&
    oneOf(row.method, ["exact", "lexical", "llm", "human"]) && rows(row.citations, citation);
}
function validLocation(value: unknown): boolean {
  return record(value) && (value.page === null || (nonnegative(value.page) && Number(value.page) >= 1)) &&
    (value.block === null || (nonnegative(value.block) && Number(value.block) >= 1)) &&
    nullableString(value.sheet) && nullableString(value.cell_range);
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
      throw new Error(`Отчёт ${runId} не найден (404): ${msg}`);
    if (res.status === 409)
      throw new Error(`Аудит ${runId} ещё не завершён (409): ${msg}`);
    throw new Error(`HTTP ${res.status}: ${msg}`);
  }
  const report = asReport(await res.json());
  if (report === null) {
    throw new Error(`GET /audits/${runId}: ответ не соответствует контракту Report`);
  }
  return report;
}

/** Durable real events, never reconstructed from a report or model counters. */
export async function fetchRunTrace(runId: string, signal?: AbortSignal): Promise<RunEvent[]> {
  const response = await fetch(`${API_BASE}/runs/${encodeURIComponent(runId)}/trace`, { signal });
  if (!response.ok) throw new Error(`Журнал HTTP ${response.status}: ${await extractErrorMessage(response)}`);
  const body: unknown = await response.json();
  if (!record(body) || body.run_id !== runId || !Array.isArray(body.events)) {
    throw new Error("Некорректный ответ журнала действий");
  }
  const events: RunEvent[] = [];
  for (const entry of body.events) {
    if (!record(entry) || typeof entry.type !== "string" ||
      (entry.run_id !== undefined && entry.run_id !== runId) || !nonnegative(entry.seq) || typeof entry.ts !== "number" ||
      !Number.isFinite(entry.ts) || !record(entry.data)) {
      throw new Error("Журнал содержит некорректное событие");
    }
    // SDK spans share the trace table, but are not public audit actions and may
    // contain internal model text. Only the documented SSE envelope is shown.
    if (entry.type === "span") continue;
    if (!isRunEventType(entry.type)) throw new Error("Неизвестный тип события журнала");
    events.push({ ...entry, run_id: runId } as RunEvent);
  }
  return events;
}
