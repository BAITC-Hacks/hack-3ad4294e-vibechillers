"use client";

import { useRef, useState } from "react";
import { CheckCircle2, FileUp, Loader2, XCircle } from "lucide-react";
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
