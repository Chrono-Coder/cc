"use client";

import Link from "next/link";
import { useState, useEffect, useCallback, useMemo } from "react";
import type { Project, TimesheetSummary } from "@/lib/api";
import { clientApi } from "@/lib/clientApi";
import { timeAgo, PALETTE, fmtHours } from "@/lib/fmt";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { StatDisplay } from "@/components/ui/stat-display";
import { EnvTag } from "@/components/ui/env-tag";
import { TermPanel } from "@/components/ui/term-panel";
import { TimeGauge } from "@/components/TimeGauge";
import { ActivityStrip } from "@/components/ActivityStrip";

export default function DashboardClient({ projects: initialProjects }: { projects: Project[] }) {
  const [projects, setProjects] = useState(initialProjects);
  const [todaySummary, setTodaySummary] = useState<TimesheetSummary[]>([]);
  const [daemonOk, setDaemonOk] = useState(true);
  const [syncOk, setSyncOk] = useState(false);
  const [ccVersion, setCcVersion] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  const fetchAll = useCallback(async () => {
    const [p, ts, h] = await Promise.allSettled([
      clientApi.projects(),
      clientApi.timesheetSummary(1),
      clientApi.health(),
    ]);
    if (p.status === "fulfilled") setProjects(p.value);
    if (ts.status === "fulfilled") setTodaySummary(ts.value);
    if (h.status === "fulfilled") {
      setDaemonOk(!!h.value.daemon);
      setSyncOk(h.value.passed?.includes?.("sync") || false);
      setCcVersion(h.value.daemon?.version ?? null);
    }
  }, []);

  useAutoRefresh(fetchAll, "env.switched");
  useEffect(() => { setMounted(true); }, []);

  const activeEnvs = useMemo(() => {
    const seen = new Set<number>();
    return projects.flatMap((p) =>
      p.environments
        .filter((e) => e.is_active)
        .map((e) => ({ ...e, project_name: p.name }))
    ).filter((e) => {
      if (seen.has(e.id)) return false;
      seen.add(e.id);
      return true;
    });
  }, [projects]);

  const recentEnvs = useMemo(() => {
    const seen = new Set<number>();
    return projects
      .flatMap((p) => p.environments.map((e) => ({ ...e, project_name: p.name })))
      .filter((e) => !e.is_active && e.last_used_at)
      .filter((e) => {
        if (seen.has(e.id)) return false;
        seen.add(e.id);
        return true;
      })
      .sort((a, b) => new Date(b.last_used_at!).getTime() - new Date(a.last_used_at!).getTime())
      .slice(0, 5);
  }, [projects]);

  const todayProjects = useMemo(() => {
    const byProject = new Map<string, number>();
    for (const s of todaySummary) byProject.set(s.project, (byProject.get(s.project) || 0) + s.minutes);
    return [...byProject.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([project, minutes], i) => ({ project, minutes, color: PALETTE[i % PALETTE.length] }));
  }, [todaySummary]);

  const totalMinutes = todayProjects.reduce((s, e) => s + e.minutes, 0);
  const totalFormatted = fmtHours(totalMinutes);

  return (
    <div className={`transition-opacity duration-700 ${mounted ? "opacity-100" : "opacity-0"}`}>

      {/* Header */}
      <div className="flex items-end justify-between mb-4">
        <div>
          <p className="section-label mb-1">dashboard</p>
          <h1 className="text-3xl font-normal text-foreground tracking-tight leading-none">
            {activeEnvs.length > 0 ? (
              <>
                <span className="font-display font-bold phosphor text-cyan-300 tabular-nums">{activeEnvs.length}</span>
                {` active environment${activeEnvs.length > 1 ? "s" : ""}`}
              </>
            ) : (
              <span className="text-muted-foreground/60">No active project</span>
            )}
          </h1>
        </div>
        <ActivityStrip count={todaySummary.length} />
      </div>

      {/* Tick strip — divider between hero and content */}
      <div aria-hidden="true" className="ticks mb-8" />

      {/* Active environments */}
      {activeEnvs.length > 0 && (
        <TermPanel
          title="active environments"
          right={
            <span className="flex items-center gap-1.5 font-mono text-[10px] text-muted-foreground/70">
              <StatusIndicator ok={true} pulse />
              <span className="tabular-nums">{activeEnvs.length} live</span>
            </span>
          }
          className="mb-6"
        >
          {activeEnvs.map((env) => (
            <Link
              key={env.id}
              href={`/env/${env.id}`}
              className="group relative flex items-center gap-3 px-4 py-3 border-b border-border/30 last:border-0"
            >
              <span
                aria-hidden
                className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[2px] rounded-full bg-cyan-400 opacity-0 scale-y-50 group-hover:opacity-100 group-hover:scale-y-100 transition-all duration-200 shadow-[0_0_8px_color-mix(in_oklch,var(--cc-cyan-400)_60%,transparent)]"
              />
              <StatusIndicator ok={true} pulse size="md" />
              <span className="text-sm font-medium text-foreground group-hover:text-cyan-400 transition-colors min-w-0 truncate">
                {env.project_name === env.name ? env.project_name : `${env.project_name} / ${env.name}`}
              </span>
              <div className="flex items-center gap-2 ml-auto shrink-0">
                {env.version && <EnvTag label={env.version} variant="zinc" />}
                {env.branch_name && <EnvTag label={env.branch_name} variant="violet" />}
                {env.database && <EnvTag label={env.database} variant="emerald" />}
              </div>
            </Link>
          ))}
        </TermPanel>
      )}

      {/* Two-column: recent + today */}
      <div className="grid grid-cols-[1fr_200px] gap-6 mb-8 items-start">
        <TermPanel title="recent">
          {recentEnvs.length === 0 ? (
            <p className="px-4 py-3 text-xs text-muted-foreground/70">No recent environments</p>
          ) : (
            recentEnvs.map((r) => (
              <Link
                key={r.id}
                href={`/env/${r.id}`}
                className="group relative flex items-center px-4 py-2.5 border-b border-border/30 last:border-0"
              >
                <span
                  aria-hidden
                  className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[2px] rounded-full bg-cyan-400 opacity-0 scale-y-50 group-hover:opacity-100 group-hover:scale-y-100 transition-all duration-200 shadow-[0_0_8px_color-mix(in_oklch,var(--cc-cyan-400)_60%,transparent)]"
                />
                <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors w-40 truncate">
                  {r.name}
                </span>
                <span className="text-[11px] text-muted-foreground/70 font-mono w-8">{r.version || ""}</span>
                <span className="text-[11px] text-muted-foreground/60 font-mono flex-1 truncate pl-3">{r.branch_name || ""}</span>
                <span className="text-[11px] text-muted-foreground/60 tabular-nums" suppressHydrationWarning>
                  {r.last_used_at ? timeAgo(r.last_used_at) : ""}
                </span>
              </Link>
            ))
          )}
        </TermPanel>

        <TermPanel title="today" bodyClassName="p-4">
          <div className="flex flex-col items-center gap-6">
            <TimeGauge entries={todayProjects} total={totalFormatted || "0m"} />

            <div className="w-full space-y-2">
              {todayProjects.map((e) => (
                <div key={e.project} className="flex items-center justify-between text-xs">
                  <span className="font-mono truncate" style={{ color: e.color }}>{e.project}</span>
                  <span className="text-muted-foreground/60 tabular-nums">{fmtHours(e.minutes)}</span>
                </div>
              ))}
            </div>

            <div className="w-full pt-4 border-t border-border/30 space-y-2">
              <StatDisplay label="projects" value={projects.length} />
              <StatDisplay label="envs" value={projects.reduce((s, p) => s + p.environments.length, 0)} />
            </div>
          </div>
        </TermPanel>
      </div>

      {/* Footer */}
      <div className="flex items-center gap-6 text-[10px] text-muted-foreground/70 font-mono border-t border-border/30 pt-4">
        <StatusIndicator ok={daemonOk} label="daemon" />
        <StatusIndicator ok={syncOk} label="sync" />
        {ccVersion && <span className="ml-auto text-muted-foreground/60">cc v{ccVersion}</span>}
      </div>
    </div>
  );
}
