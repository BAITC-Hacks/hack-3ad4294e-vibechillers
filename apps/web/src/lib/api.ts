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
