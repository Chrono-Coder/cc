"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useEvents } from "@/hooks/useEvents";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell, PieChart, Pie,
} from "recharts";
import type { CSSProperties } from "react";
import type { TimesheetSummary } from "@/lib/api";
import { cn } from "@/lib/utils";
import { colorFor, fmtHours, fmtDate } from "@/lib/fmt";
import { StatDisplay } from "@/components/ui/stat-display";
import { TermPanel } from "@/components/ui/term-panel";

const RANGES = [7, 14, 30, 90];

/* Chart chrome rides the theme tokens — never literal grays (chrono remaps cyan→yellow). */
const TOOLTIP_STYLE: CSSProperties = {
  background: "var(--popover)",
  border: "1px solid var(--border)",
  borderRadius: 6,
  fontSize: 12,
};
const TOOLTIP_ITEM = { color: "var(--muted-foreground)", fontSize: 12 };
const AXIS_TICK = {
  fill: "var(--muted-foreground)",
  fillOpacity: 0.55,
  fontSize: 10,
  fontFamily: "var(--font-plex-mono), monospace",
};

export default function TimesheetClient({
  summary,
  days,
}: {
  summary: TimesheetSummary[];
  days: number;
}) {
  const router = useRouter();
  const { subscribe } = useEvents();
  // Live-refresh the charts when an env is switched elsewhere.
  useEffect(() => subscribe("env.switched", () => router.refresh()), [subscribe, router]);

  const projects = [...new Set(summary.map((e) => e.project))].sort();

  const byDate: Record<string, Record<string, number>> = {};
  for (const entry of summary) {
    if (!byDate[entry.date]) byDate[entry.date] = {};
    byDate[entry.date][entry.project] = (byDate[entry.date][entry.project] ?? 0) + entry.minutes;
  }
  const dailyData = Object.entries(byDate)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, projs]) => ({ date, ...projs }));

  const totals: Record<string, number> = {};
  for (const entry of summary) {
    totals[entry.project] = (totals[entry.project] ?? 0) + entry.minutes;
  }
  const pieData = Object.entries(totals)
    .sort(([, a], [, b]) => b - a)
    .map(([name, minutes]) => ({ name, minutes }));

  const totalMins = Object.values(totals).reduce((s, v) => s + v, 0);
  const avgPerDay = dailyData.length > 0 ? Math.round(totalMins / dailyData.length) : 0;

  const Y_MAX = 480;
  const yTicks = [0, 120, 240, 360, 480];

  if (summary.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-40 text-center gap-3">
        <p className="font-mono text-muted-foreground/60 text-lg">no data</p>
        <p className="text-muted-foreground/70 text-sm">Switch some projects and come back.</p>
      </div>
    );
  }

  const rangeChips = (
    <span className="flex items-center gap-1">
      {RANGES.map((r) => (
        <button
          key={r}
          onClick={() => router.push(`/timesheet?days=${r}`)}
          className={cn(
            "px-2 py-0.5 text-[11px] font-mono rounded-[3px] border transition-colors cursor-pointer",
            days === r
              ? "text-cyan-300 border-cyan-400/40"
              : "text-muted-foreground/60 border-transparent hover:text-muted-foreground"
          )}
        >
          {r}d
        </button>
      ))}
    </span>
  );

  return (
    <div>
      {/* Hero — stays outside the panels, landing grammar */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="section-label">timesheet</span>
        </div>
        {/* The page's one glow — hero total in dot-matrix */}
        <h1 className="font-display phosphor text-5xl font-semibold text-foreground tracking-tight leading-none tabular-nums">
          {fmtHours(totalMins)}
        </h1>
      </div>

      {/* Tick strip — divider between hero and content */}
      <div aria-hidden="true" className="ticks mb-8" />

      <div className="space-y-8">
        {/* Stats + donut */}
        <TermPanel title="summary" right={rangeChips} bodyClassName="p-4">
          <div className="grid grid-cols-[1fr_200px] gap-12">
            <div className="space-y-2">
              <StatDisplay label="total tracked" value={fmtHours(totalMins)} accent />
              <StatDisplay label="projects" value={projects.length} />
              <StatDisplay label="active days" value={dailyData.length} />
              <StatDisplay label="avg / day" value={fmtHours(avgPerDay)} />
            </div>

            {/* Donut */}
            <div className="flex flex-col items-center">
              <div className="relative w-40 h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="minutes"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={68}
                      paddingAngle={2}
                      strokeWidth={0}
                    >
                      {pieData.map((entry) => (
                        <Cell key={entry.name} fill={colorFor(entry.name, projects)} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ ...TOOLTIP_STYLE, padding: "6px 10px" }}
                      itemStyle={TOOLTIP_ITEM}
                      formatter={(val: unknown, name: unknown) => [fmtHours(Number(val)), String(name)]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </TermPanel>

        {/* Daily breakdown */}
        <TermPanel title="daily breakdown" bodyClassName="p-4">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={dailyData} barSize={dailyData.length > 20 ? 8 : 16} barGap={1} barCategoryGap="20%">
              <XAxis
                dataKey="date"
                tickFormatter={fmtDate}
                tick={AXIS_TICK}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                ticks={yTicks}
                domain={[0, Y_MAX]}
                tickFormatter={(v) => v === 0 ? "" : `${v / 60}h`}
                tick={AXIS_TICK}
                axisLine={false}
                tickLine={false}
                width={28}
              />
              <Tooltip
                contentStyle={{ ...TOOLTIP_STYLE, padding: "8px 12px" }}
                labelStyle={{ color: "var(--muted-foreground)", opacity: 0.7, fontSize: 11, marginBottom: 4 }}
                labelFormatter={(label) => fmtDate(String(label))}
                formatter={(val: unknown, name: unknown) => [fmtHours(Number(val)), String(name)]}
                itemStyle={TOOLTIP_ITEM}
                cursor={{ fill: "var(--foreground)", fillOpacity: 0.04 }}
              />
              {projects.map((proj) => (
                <Bar key={proj} dataKey={proj} fill={colorFor(proj, projects)} radius={[2, 2, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </TermPanel>

        {/* Project totals */}
        <TermPanel title="by project" bodyClassName="p-0">
          {pieData.map((entry) => {
            const pct = Math.round((entry.minutes / totalMins) * 100);
            return (
              <Link
                key={entry.name}
                href={`/projects?q=${encodeURIComponent(entry.name)}`}
                className="group flex items-center py-3 px-4 border-l-2 border-l-transparent hover:border-l-cyan-400/80 border-b border-border/50 last:border-b-0 transition-colors"
              >
                <span
                  className="w-1.5 h-1.5 rounded-full shrink-0 mr-3"
                  style={{ background: colorFor(entry.name, projects) }}
                />
                <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors font-mono truncate flex-1">
                  {entry.name}
                </span>
                <span className="text-[11px] text-muted-foreground/70 font-mono tabular-nums w-10 text-right mr-4">
                  {pct}%
                </span>
                <span className="text-sm text-muted-foreground font-bold tabular-nums w-16 text-right">
                  {fmtHours(entry.minutes)}
                </span>
              </Link>
            );
          })}
        </TermPanel>
      </div>
    </div>
  );
}
