"use client";

import { useState } from "react";
import { Bot, GitCompareArrows, MessagesSquare, Server } from "lucide-react";
import { API_BASE } from "../lib/api";
import { AuditWorkspace } from "../components/AuditWorkspace";
import { ChatWorkspace } from "../components/ChatWorkspace";

type Tab = "audit" | "chat";

export default function Home() {
  const [tab, setTab] = useState<Tab>("audit");

  const tabClass = (t: Tab): string =>
    `flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs transition-colors ${
      tab === t
        ? "bg-neutral-800 text-neutral-100"
        : "text-neutral-400 hover:bg-neutral-900 hover:text-neutral-200"
    }`;

  return (
    <main className="flex min-h-screen flex-col bg-neutral-950 text-neutral-100">
      <header className="flex flex-wrap items-center gap-3 border-b border-neutral-800/80 px-4 py-2">
        <div className="flex items-center gap-2 font-semibold tracking-tight">
          <Bot size={17} className="text-sky-400" />
          Function Lineage Auditor
        </div>
        <nav className="flex items-center gap-1" aria-label="Рабочее пространство">
          <button
            type="button"
            onClick={() => setTab("audit")}
            aria-pressed={tab === "audit"}
            className={tabClass("audit")}
          >
            <GitCompareArrows size={13} />
            Аудит реорганизации
          </button>
          <button
            type="button"
            onClick={() => setTab("chat")}
            aria-pressed={tab === "chat"}
            className={tabClass("chat")}
          >
            <MessagesSquare size={13} />
            Поиск по документам (отдельный режим)
          </button>
        </nav>
        <span className="ml-auto hidden items-center gap-1 font-mono text-[11px] text-neutral-500 sm:flex">
          <Server size={10} className="text-neutral-600" />
          {API_BASE}
        </span>
      </header>

      {/* Both stay mounted so switching tabs never drops a running stream or a report. */}
      <div hidden={tab !== "audit"}>
        <AuditWorkspace />
      </div>
      <div hidden={tab !== "chat"}>
        <ChatWorkspace />
      </div>
    </main>
  );
}
