"use client";

import { useEffect, useRef, useState } from "react";
import type { ConnectionStatus } from "@/types/edital";
import type { LogLine } from "./CockpitDashboard";

const LEVEL_COLOR: Record<string, string> = {
  DEBUG:   "text-zinc-500",
  INFO:    "text-green-400",
  WARNING: "text-yellow-400",
  ERROR:   "text-red-400",
};

const LEVEL_PREFIX: Record<string, string> = {
  DEBUG:   "[DBG]",
  INFO:    "[INF]",
  WARNING: "[WRN]",
  ERROR:   "[ERR]",
};

interface Props {
  logs: LogLine[];
  connStatus: ConnectionStatus;
}

export default function HackerTerminal({ logs, connStatus }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Autoscroll on new logs
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="flex flex-col h-full bg-black relative terminal-scanline terminal-crt">
      {/* Terminal topbar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-800 bg-zinc-950/80 shrink-0 z-10">
        <span className="h-3 w-3 rounded-full bg-red-500/80" />
        <span className="h-3 w-3 rounded-full bg-yellow-500/80" />
        <span className="h-3 w-3 rounded-full bg-green-500/80" />
        <span className="ml-3 text-xs text-zinc-500 font-mono">
          cockpit@estudohub — stream
        </span>
        <span
          className={`ml-auto text-xs font-mono ${
            connStatus === "connected" ? "text-green-400 terminal-glow" : "text-zinc-600"
          }`}
        >
          {connStatus === "connected" ? "● LIVE" : "○ OFFLINE"}
        </span>
      </div>

      {/* Log output area */}
      <div className="flex-1 overflow-y-auto p-4 font-mono text-sm space-y-0.5 relative z-10 scrollbar-thin">
        {logs.map((line) => (
          <div key={line.id} className="flex gap-2 leading-5">
            <span className="text-zinc-600 shrink-0 select-none" suppressHydrationWarning>{line.ts}</span>
            <span
              className={`shrink-0 select-none font-semibold ${
                LEVEL_COLOR[line.level] ?? "text-green-400"
              }`}
            >
              {LEVEL_PREFIX[line.level] ?? "[INF]"}
            </span>
            <span
              className={`break-all ${
                line.level === "ERROR"
                  ? "text-red-300"
                  : line.level === "WARNING"
                  ? "text-yellow-300"
                  : "text-green-300"
              }`}
            >
              {line.message}
            </span>
          </div>
        ))}

        {/* Blinking cursor at bottom */}
        <div className="flex gap-2 leading-5 mt-1">
          <span className="text-zinc-600 select-none" suppressHydrationWarning>
            {mounted ? new Date().toLocaleTimeString("pt-BR", { hour12: false }) : ""}
          </span>
          <span className="text-green-400 terminal-glow">
            <span className="cursor-blink">█</span>
          </span>
        </div>

        <div ref={bottomRef} />
      </div>

      {/* Subtle green vignette glow at bottom */}
      <div
        className="absolute bottom-0 left-0 right-0 h-16 pointer-events-none z-0"
        style={{
          background:
            "linear-gradient(to top, rgba(74,222,128,0.04) 0%, transparent 100%)",
        }}
      />
    </div>
  );
}
