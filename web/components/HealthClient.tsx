"use client";

import { useState } from "react";
import type { HealthReport, HealthIssue, DaemonHealth } from "@/lib/api";
import CopyButton from "@/components/CopyButton";
import { fmtUptime, fmtBytes } from "@/lib/fmt";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { TermPanel } from "@/components/ui/term-panel";
import {
  ExclamationTriangleIcon,
  CheckIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function DropButton({ name, onDropped }: { name: string; onDropped: () => void }) {
  const [state, setState] = useState<"idle" | "confirming" | "dropping" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function drop() {
    setState("dropping");
    const res = await fetch("/api/health/dropdb", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const data = await res.json();
    if (res.ok || (data.error ?? "").toLowerCase().includes("does not exist")) {
      onDropped();
    } else {
      setError(data.error ?? "Failed");
      setState("error");
    }
  }

  if (state === "error") return (
    <span className="text-xs text-red-400 shrink-0 max-w-40 truncate cursor-default" title={error ?? ""}>{error}</span>
  );
  if (state === "dropping") return (
    <span className="text-xs text-muted-foreground/60 shrink-0">dropping...</span>
  );
  if (state === "confirming") return (
    <div className="flex items-center gap-1.5 shrink-0">
      <span className="text-xs text-amber-400">drop?</span>
      <button onClick={drop} className="text-xs text-red-400 hover:text-red-300 cursor-pointer px-1">yes</button>
      <button onClick={() => setState("idle")} className="text-xs text-muted-foreground/60 hover:text-muted-foreground cursor-pointer px-1">no</button>
    </div>
  );
  return (
    <button
      onClick={() => setState("confirming")}
      title={`Drop database ${name}`}
      className="opacity-0 group-hover:opacity-100 text-muted-foreground/70 hover:text-red-400 cursor-pointer shrink-0 transition-colors"
    >
      <TrashIcon className="w-3.5 h-3.5" />
    </button>
  );
}

function DaemonStats({ daemon }: { daemon: DaemonHealth | undefined }) {
  return (
    <TermPanel
      title="daemon"
      right={
        <StatusIndicator
          ok={!!daemon}
          pulse={!!daemon}
          label={daemon ? "online" : "offline"}
          className="font-mono text-[11px] text-muted-foreground"
        />
      }
      bodyClassName="px-4 py-3"
    >
      {daemon ? (
        <div className="flex items-center gap-6 text-xs flex-wrap">
          <span className="text-muted-foreground/60">uptime <span className="text-muted-foreground font-mono ml-1">{fmtUptime(daemon.uptime_seconds)}</span></span>
          <span className="text-muted-foreground/60">RPCs <span className="text-muted-foreground font-mono ml-1">{daemon.rpc_count.toLocaleString()}</span></span>
          {daemon.db_size_bytes != null && (
            <span className="text-muted-foreground/60">DB <span className="text-muted-foreground font-mono ml-1">{fmtBytes(daemon.db_size_bytes)}</span></span>
          )}
          {daemon.last_error && (
            <span className="text-amber-400/80 font-mono text-[11px] truncate max-w-64" title={daemon.last_error}>
              {daemon.last_error}
            </span>
          )}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground/60">daemon offline</p>
      )}
    </TermPanel>
  );
}

function IssueBlock({ issue }: { issue: HealthIssue }) {
  const [dropped, setDropped] = useState<Set<string>>(new Set());
  const isError = issue.severity === "error";
  const entries = issue.items.map((item, i) => ({
    item,
    key: issue.keys?.[i] ?? `${item.split(/[\s(]/)[0].trim()}_${i}`,
  }));
  const visibleEntries = entries.filter(({ key }) => !dropped.has(key));

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <ExclamationTriangleIcon className={cn("w-3.5 h-3.5 shrink-0", isError ? "text-red-400" : "text-amber-400")} />
        <div className="flex-1 min-w-0">
          <span className={cn("text-sm", isError ? "text-red-400" : "text-amber-400")}>{issue.title}</span>
          <span className="text-muted-foreground/70 text-xs ml-2">{visibleEntries.length}</span>
        </div>
      </div>
      <p className="text-xs text-muted-foreground/60 pl-6">{issue.description}</p>
      <div className="pl-6 space-y-0 max-h-64 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {visibleEntries.map(({ item, key }) => (
          <div key={key} className="group flex items-center gap-2 py-2 -ml-3 border-l-2 border-l-transparent pl-2.5 border-b border-border/50 last:border-b-0 hover:border-l-cyan-400/60 transition-colors">
            <span className={cn("w-1 h-1 rounded-full shrink-0", isError ? "bg-red-500/60" : "bg-amber-500/60")} />
            <span className="font-mono text-xs text-muted-foreground flex-1 min-w-0 truncate">{item}</span>
            <CopyButton text={key} size="w-3 h-3" className="opacity-0 group-hover:opacity-100 text-muted-foreground/70 hover:text-muted-foreground" />
            {issue.droppable && (
              <DropButton name={key} onDropped={() => setDropped((prev) => new Set([...prev, key]))} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function HealthClient({ report }: { report: HealthReport }) {
  const errors = report.issues.filter((i) => i.severity === "error");
  const warnings = report.issues.filter((i) => i.severity === "warning");
  const allClear = report.issues.length === 0;

  return (
    <div className="">
      {/* Hero */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="section-label">diagnostics</span>
        </div>
        <div className="flex items-end justify-between">
          <h1 className="text-3xl font-normal text-foreground tracking-tight">Health</h1>
          <div className="flex items-center gap-3 text-xs">
            {errors.length > 0 && (
              <span className="text-red-400">{errors.length} error{errors.length !== 1 ? "s" : ""}</span>
            )}
            {warnings.length > 0 && (
              <span className="text-amber-400">{warnings.length} warning{warnings.length !== 1 ? "s" : ""}</span>
            )}
            {allClear && (
              <StatusIndicator ok={true} label="all clear" />
            )}
          </div>
        </div>
        {!allClear && (
          <p className="text-sm text-muted-foreground mt-2">
            Review each issue below — droppable databases have an inline action; the rest list the affected items to fix.
          </p>
        )}
      </div>

      {/* Tick strip — divider between hero and content */}
      <div aria-hidden="true" className="ticks mb-8" />

      {/* Daemon stats */}
      <DaemonStats daemon={report.daemon} />

      {/* Issues */}
      {allClear ? (
        <TermPanel
          title="checks"
          right={
            <span className="font-mono text-[11px] tabular-nums text-emerald-400/80">
              {report.passed.length} passed
            </span>
          }
          className="mt-6"
        >
          <div className="py-16 text-center">
            <CheckIcon className="w-8 h-8 text-emerald-500/70 mx-auto mb-3" />
            <p className="text-sm text-foreground/70">Everything looks good</p>
            <p className="text-xs text-muted-foreground/70 mt-1">All {report.passed.length} checks passed</p>
          </div>
        </TermPanel>
      ) : (
        <div className="mt-6 space-y-6">
          {errors.length > 0 && (
            <TermPanel
              title="errors"
              right={<span className="font-mono text-[11px] tabular-nums text-red-400">{errors.length}</span>}
              bodyClassName="p-4"
            >
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {errors.map((issue) => <IssueBlock key={issue.id} issue={issue} />)}
              </div>
            </TermPanel>
          )}
          {warnings.length > 0 && (
            <TermPanel
              title="warnings"
              right={<span className="font-mono text-[11px] tabular-nums text-amber-400">{warnings.length}</span>}
              bodyClassName="p-4"
            >
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {warnings.map((issue) => <IssueBlock key={issue.id} issue={issue} />)}
              </div>
            </TermPanel>
          )}
        </div>
      )}

      {/* Passed checks */}
      {report.passed.length > 0 && !allClear && (
        <TermPanel
          title="passed"
          right={<span className="font-mono text-[11px] tabular-nums text-emerald-400/80">{report.passed.length}</span>}
          className="mt-6"
          bodyClassName="px-4 py-1"
        >
          <div className="space-y-0">
            {report.passed.map((check, i) => (
              <div key={i} className="flex items-center gap-3 py-2.5 -ml-3 border-l-2 border-l-transparent pl-2.5 border-b border-border/50 last:border-b-0 hover:border-l-cyan-400/60 transition-colors">
                <CheckIcon className="w-3.5 h-3.5 text-emerald-500/70 shrink-0" />
                <span className="text-xs text-muted-foreground">{check}</span>
              </div>
            ))}
          </div>
        </TermPanel>
      )}
    </div>
  );
}
