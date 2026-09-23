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
    `flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400 ${
      tab === t
        ? "bg-neutral-800 text-white"
        : "text-neutral-300 hover:bg-neutral-900 hover:text-white"
    }`;

  return (
    <main className="flex min-h-screen flex-col bg-neutral-950 text-neutral-100">
      <header className="flex flex-wrap items-center gap-4 border-b border-neutral-800/70 bg-neutral-900/40 px-5 py-4">
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
        <span className="ml-auto hidden items-center gap-2 font-mono text-xs text-neutral-400 sm:flex">
          <Server size={12} className="text-neutral-400" />
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
