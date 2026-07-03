"use client";

import { useState, useEffect, useCallback } from "react";
import { useEvents } from "@/hooks/useEvents";
import CopyButton from "@/components/CopyButton";
import GitHubIcon from "@/components/icons/GitHubIcon";
import {
  ArrowTopRightOnSquareIcon,
  CloudIcon,
  PlayIcon,
  ClockIcon,
} from "@heroicons/react/24/outline";
import { EnvTag } from "@/components/ui/env-tag";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { cn } from "@/lib/utils";
import { timeAgo } from "@/lib/fmt";

function versionColor(name: string | undefined): string {
  if (!name) return "text-muted-foreground";
  const major = parseInt(name.split(".")[0], 10);
  const palette: Record<number, string> = {
    18: "bg-violet-950/40 text-violet-400 border-violet-800/30",
    17: "bg-blue-950/40 text-blue-400 border-blue-800/30",
    16: "bg-cyan-950/40 text-cyan-400 border-cyan-800/30",
    15: "bg-teal-950/40 text-teal-400 border-teal-800/30",
    14: "bg-emerald-950/40 text-emerald-400 border-emerald-800/30",
    13: "bg-yellow-950/40 text-yellow-400 border-yellow-800/30",
  };
  return palette[major] ?? "bg-orange-950/40 text-orange-400 border-orange-800/30";
}

export type EnvData = {
  id: number;
  name: string;
  project_path: string;
  github_url: string | null;
  branch_name: string | null;
  last_used_at: string | null;
  last_login_at: string | null;
  is_active: boolean;
  is_virtual: boolean;
  pinned: boolean;
  status: string;
  sh_url: string | null;
  notes: string | null;
  ticket_ids: string[];
  project: { id: number; name: string };
  version: { name: string; port: string | null; path: string | null } | null;
  database: string | null;
  modules: { id: number; name: string }[];
};

const STATUS_STYLE: Record<string, string> = {
  active:
    "bg-emerald-950/40 text-emerald-400 shadow-[inset_0_0_12px_color-mix(in_oklch,var(--cc-emerald-400)_15%,transparent)]",
  merged:
    "bg-violet-950/40 text-violet-300 shadow-[inset_0_0_12px_color-mix(in_oklch,var(--cc-violet-400)_15%,transparent)]",
  archived: "bg-muted text-muted-foreground",
};

export default function EnvDetail({ env: initialEnv }: { env: EnvData }) {
  const [env, setEnv] = useState<EnvData>(initialEnv);
  const { subscribe } = useEvents();

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`/api/env/${initialEnv.id}`, { cache: "no-store" });
      if (res.ok) setEnv(await res.json());
    } catch { /* ignore */ }
  }, [initialEnv.id]);

  useEffect(() => {
    return subscribe("env.switched", () => refresh());
  }, [subscribe, refresh]);

  const port = env.version?.port;
  const [pinned, setPinned] = useState(env.pinned);

  async function togglePin() {
    const res = await fetch(`/api/env/${env.id}/pin`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      setPinned(data.pinned);
    }
  }

  const [status, setStatus] = useState(env.status || "active");
  const [savingStatus, setSavingStatus] = useState(false);

  async function changeStatus(next: string) {
    if (next === status || savingStatus) return;
    setSavingStatus(true);
    const res = await fetch(`/api/env/${env.id}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: next }),
    });
    if (res.ok) setStatus(((await res.json()) as { status: string }).status);
    setSavingStatus(false);
  }

  const timestamp = env.last_login_at
    ? `login ${timeAgo(env.last_login_at)}`
    : env.last_used_at
      ? timeAgo(env.last_used_at)
      : null;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2.5 mb-2">
          <span className="section-label">environment</span>
          {env.is_active && <StatusIndicator ok={true} pulse size="md" />}
        </div>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-baseline gap-4">
            <h1
              className={cn(
                "text-5xl font-semibold text-foreground tracking-tight leading-none",
                env.is_active && "phosphor"
              )}
            >
              {env.name}
            </h1>
            <div className="flex items-center gap-2 translate-y-0.5">
              <CopyButton text={env.name} className="text-muted-foreground/70 hover:text-muted-foreground" />
              <button
                onClick={togglePin}
                title={pinned ? "Unpin" : "Pin"}
                className={cn(
                  "text-base cursor-pointer transition-colors",
                  pinned ? "text-amber-400" : "text-muted-foreground/60 hover:text-amber-400"
                )}
              >
                ★
              </button>
            </div>
          </div>
          {port && (
            <a
              href={`http://localhost:${port}/web`}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(
                "shrink-0 flex items-center justify-center w-9 h-9 rounded-[3px] transition-all border",
                env.is_active
                  ? "text-cyan-500 border-cyan-800/40 hover:text-cyan-400 hover:border-cyan-800/70 hover:shadow-[0_0_14px_color-mix(in_oklch,var(--cc-cyan-400)_20%,transparent)]"
                  : "text-muted-foreground/70 border-border/50 hover:text-cyan-400 hover:border-cyan-800/40"
              )}
              title={`localhost:${port}`}
            >
              <ArrowTopRightOnSquareIcon className="w-4 h-4" />
            </a>
          )}
        </div>
      </div>

      {/* Tags row */}
      <div className="flex items-center gap-2 flex-wrap">
        {env.version && (
          <span
            className={cn(
              "px-2.5 py-1 rounded-[3px] border font-display text-sm font-bold leading-4",
              versionColor(env.version.name)
            )}
          >
            {env.version.name}
          </span>
        )}
        {env.branch_name && <EnvTag label={env.branch_name} variant="violet" />}
        {env.database && <EnvTag label={env.database} variant="emerald" />}
        {env.is_active && (
          <span className="px-2.5 py-1 rounded-[3px] border text-xs font-mono bg-cyan-950/30 text-cyan-400/80 border-cyan-800/30 shadow-[0_0_10px_color-mix(in_oklch,var(--cc-cyan-400)_12%,transparent)]">
            active
          </span>
        )}
        {/* Lifecycle status — controls whether the env shows in the switch picker */}
        <div
          className="inline-flex items-center rounded-[3px] border border-border/50 overflow-hidden"
          role="group"
          aria-label="Environment status"
        >
          {(["active", "merged", "archived"] as const).map((s) => (
            <button
              key={s}
              onClick={() => changeStatus(s)}
              disabled={savingStatus}
              title={`Set status: ${s}`}
              className={cn(
                "px-2.5 py-1 text-xs font-mono capitalize transition-all cursor-pointer disabled:opacity-50",
                status === s ? STATUS_STYLE[s] : "text-muted-foreground/50 hover:text-foreground"
              )}
            >
              {s}
            </button>
          ))}
        </div>
        {timestamp && (
          <span className="text-xs text-muted-foreground/70 ml-2 flex items-center gap-1" suppressHydrationWarning>
            <ClockIcon className="w-3 h-3" />
            {timestamp}
          </span>
        )}
      </div>

      {/* External links */}
      {!env.is_virtual && (env.github_url || env.sh_url || env.branch_name) && (
        <div className="flex items-center gap-4">
          {env.github_url && (
            <a
              href={env.branch_name ? `${env.github_url}/tree/${env.branch_name}` : env.github_url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-center gap-2 text-sm text-muted-foreground hover:text-cyan-400 transition-colors"
            >
              <GitHubIcon className="w-4 h-4" />
              <span>GitHub</span>
              <ArrowTopRightOnSquareIcon className="w-3 h-3 opacity-0 group-hover:opacity-60 transition-opacity" />
            </a>
          )}
          {env.sh_url && (
            <a
              href={env.sh_url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-center gap-2 text-sm text-muted-foreground hover:text-cyan-400 transition-colors"
            >
              <CloudIcon className="w-4 h-4" />
              <span>Odoo SH</span>
              <ArrowTopRightOnSquareIcon className="w-3 h-3 opacity-0 group-hover:opacity-60 transition-opacity" />
            </a>
          )}
          {env.branch_name && (
            <a
              href={`https://psxrunbot.odoo.com/runbot/bundle/${env.branch_name}`}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-center gap-2 text-sm text-muted-foreground hover:text-cyan-400 transition-colors"
            >
              <PlayIcon className="w-4 h-4" />
              <span>Runbot</span>
              <ArrowTopRightOnSquareIcon className="w-3 h-3 opacity-0 group-hover:opacity-60 transition-opacity" />
            </a>
          )}
        </div>
      )}
    </div>
  );
}
