"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { TermPanel } from "@/components/ui/term-panel";

type LogEntry = {
  timestamp: string;
  level: string;
  source: string;
  message: string;
};

const SOURCES = ["all", "rpc"] as const;
const LEVELS = ["all", "debug", "info", "warning", "error"] as const;

const LEVEL_COLOR: Record<string, string> = {
  debug: "text-muted-foreground/60",
  info: "text-cyan-400/80",
  warning: "text-amber-400/80",
  error: "text-red-400/80",
};

const ROW_STYLE: Record<string, string> = {
  debug: "text-muted-foreground/60",
  info: "text-muted-foreground",
  warning: "text-foreground/70",
  error: "text-foreground/70",
};

export default function LogsClient({ initialLogs }: { initialLogs: LogEntry[] }) {
  const [logs, setLogs] = useState<LogEntry[]>(initialLogs);
  const [source, setSource] = useState<string>("all");
  const [level, setLevel] = useState<string>("all");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lines, setLines] = useState(200);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  const fetchLogs = useCallback(async () => {
    const params = new URLSearchParams({ source, lines: String(lines) });
    if (level !== "all") params.set("level", level);
    try {
      const res = await fetch(`/api/logs?${params}`, { cache: "no-store" });
      if (res.ok) setLogs(await res.json());
    } catch { /* ignore */ }
  }, [source, level, lines]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(fetchLogs, 2000);
    return () => clearInterval(id);
  }, [autoRefresh, fetchLogs]);

  useEffect(() => {
    if (stickToBottom.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    stickToBottom.current = scrollHeight - scrollTop - clientHeight < 40;
  };

  const tabCls = (active: boolean) => cn(
    "px-2 py-0.5 text-[11px] font-mono capitalize transition-colors cursor-pointer rounded-[3px] border",
    active
      ? "text-cyan-300 border-cyan-400/40"
      : "text-muted-foreground/60 border-transparent hover:text-muted-foreground"
  );

  /* Chrome-bar controls — live/source/level chips live in the panel title bar */
  const controls = (
    <>
      <div className="flex gap-0.5">
        {SOURCES.map((s) => (
          <button key={s} onClick={() => setSource(s)} className={tabCls(source === s)}>
            {s === "all" ? "All Logs" : "RPC"}
          </button>
        ))}
      </div>

      <span aria-hidden className="w-px h-4 bg-border" />

      <div className="flex gap-0.5">
        {LEVELS.map((l) => (
          <button key={l} onClick={() => setLevel(l)} className={tabCls(level === l)}>
            {l}
          </button>
        ))}
      </div>

      <span aria-hidden className="w-px h-4 bg-border" />

      <select
        value={lines}
        onChange={(e) => setLines(Number(e.target.value))}
        className="bg-transparent text-[11px] font-mono text-muted-foreground/60 cursor-pointer outline-none"
      >
        {[100, 200, 500, 1000].map((n) => (
          <option key={n} value={n} className="bg-background">
            {n} lines
          </option>
        ))}
      </select>

      <span aria-hidden className="w-px h-4 bg-border" />

      <button
        onClick={() => setAutoRefresh(!autoRefresh)}
        className={cn(
          "flex items-center gap-1.5 px-2 py-0.5 rounded-[3px] text-[11px] font-mono cursor-pointer transition-colors",
          autoRefresh ? "text-cyan-400" : "text-muted-foreground/70 hover:text-muted-foreground"
        )}
      >
        <span className={cn("w-1.5 h-1.5 rounded-full", autoRefresh ? "bg-cyan-400 animate-pulse" : "bg-muted-foreground/60")} />
        Live
      </button>

      <button
        onClick={fetchLogs}
        className="px-2 py-0.5 rounded-[3px] text-[11px] font-mono text-muted-foreground/70 hover:text-muted-foreground transition-colors cursor-pointer"
      >
        Refresh
      </button>
    </>
  );

  return (
    <div className="">
      {/* Hero */}
      <div className="mb-4">
        <p className="section-label mb-1">logs</p>
        <div className="flex items-end gap-12">
          <div>
            <p className="text-4xl font-display font-bold phosphor text-foreground tabular-nums leading-none">{logs.length}</p>
            <p className="text-xs text-muted-foreground mt-2">entries</p>
          </div>
        </div>
      </div>

      {/* Tick strip — divider between hero and content */}
      <div aria-hidden="true" className="ticks mb-8" />

      {/* Log viewer — THE terminal surface */}
      <TermPanel title="~/.cc-cli/logs" right={controls} scanlines bodyClassName="bg-sidebar">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="h-[calc(100vh-320px)] overflow-y-auto px-3 font-mono text-xs leading-relaxed [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          {logs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground/70">
              No log entries found
            </div>
          ) : (
            <table className="w-full">
              <tbody>
                {logs.map((entry, i) => (
                  <tr
                    key={i}
                    className="border-l-2 border-l-transparent hover:border-l-cyan-400/60 hover:bg-muted/30 transition-colors border-b border-border/30 last:border-b-0"
                  >
                    <td className="pl-2 pr-0 py-1.5 text-muted-foreground/70 whitespace-nowrap align-top w-[180px] tabular-nums">
                      {entry.timestamp}
                    </td>
                    <td className="px-3 py-1.5 align-top w-[60px]">
                      <span className={cn("text-[10px] uppercase font-medium", LEVEL_COLOR[entry.level] || LEVEL_COLOR.debug)}>
                        {entry.level}
                      </span>
                    </td>
                    <td className={cn("py-1.5 break-all", ROW_STYLE[entry.level] || "text-muted-foreground")}>
                      {entry.message}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </TermPanel>
    </div>
  );
}
