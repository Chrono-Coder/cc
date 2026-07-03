"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useEvents } from "@/hooks/useEvents";
import { fmtTime, fmtDayHeader } from "@/lib/fmt";
import type { HistoryEntry } from "@/lib/api";
import { StopIcon, TrashIcon, CheckIcon } from "@heroicons/react/24/outline";
import { colorFor, fmtDuration, withAlpha } from "@/lib/fmt";
import { toast } from "sonner";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { cn } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { SectionHeader } from "@/components/ui/section-header";
import { EnvTag } from "@/components/ui/env-tag";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { TermPanel } from "@/components/ui/term-panel";

const RANGES = [7, 14, 30, 90];
const DAYS_PER_PAGE = 10;

function pageHref(days: number, page: number) {
  return `/history?days=${days}&page=${page}`;
}

function buildPageNumbers(current: number, total: number): (number | "ellipsis")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | "ellipsis")[] = [1];
  if (current > 3) pages.push("ellipsis");
  for (let p = Math.max(2, current - 1); p <= Math.min(total - 1, current + 1); p++) pages.push(p);
  if (current < total - 2) pages.push("ellipsis");
  pages.push(total);
  return pages;
}

export default function HistoryClient({ entries, days, page }: { entries: HistoryEntry[]; days: number; page: number }) {
  const router = useRouter();
  const { subscribe } = useEvents();
  // Live-refresh when an env is switched elsewhere (CLI / other tab).
  useEffect(() => subscribe("env.switched", () => router.refresh()), [subscribe, router]);
  const [deleted, setDeleted] = useState<Set<number>>(new Set());
  const timers = useState<Map<number, ReturnType<typeof setTimeout>>>(() => new Map())[0];
  const [stopping, setStopping] = useState(false);
  const [clearingFlags, setClearingFlags] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTime, setEditTime] = useState("");
  const [editNote, setEditNote] = useState("");
  const [now] = useState(() => Date.now());

  function startEdit(entry: EntryWithDuration) {
    setEditingId(entry.id);
    setEditTime(fmtTime(entry.switched_at));
    setEditNote(entry.note ?? "");
  }

  async function saveEdit(entry: EntryWithDuration) {
    if (!editTime) { setEditingId(null); return; }
    const [h, m] = editTime.split(":").map(Number);
    const date = new Date(entry.switched_at);
    date.setHours(h, m, 0, 0);
    // Edit start time + note together; editing an auto entry promotes it to
    // authoritative server-side (timesheet.update_entry sets `edited`).
    await fetch("/api/history", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: entry.id, switched_at: date.toISOString(), note: editNote }),
    });
    setEditingId(null);
    router.refresh();
  }

  async function stopTimesheet() {
    setStopping(true);
    await fetch("/api/history", { method: "POST" });
    setStopping(false);
    router.refresh();
  }

  async function clearFlags() {
    setClearingFlags(true);
    const res = await fetch("/api/history/clear-flags", { method: "POST" });
    setClearingFlags(false);
    if (res.ok) {
      const data = await res.json().catch(() => ({}));
      toast(`Cleared ${data.cleared ?? 0} flag${data.cleared === 1 ? "" : "s"}`);
      router.refresh();
    } else {
      toast("Failed to clear flags");
    }
  }

  function deleteEntry(id: number) {
    setDeleted((prev) => new Set(prev).add(id));
    const timer = setTimeout(async () => {
      await fetch(`/api/history?id=${id}`, { method: "DELETE" });
      timers.delete(id);
    }, 4000);
    timers.set(id, timer);
    toast("Entry deleted", {
      action: { label: "Undo", onClick: () => undoDelete(id) },
      duration: 4000,
    });
  }

  function undoDelete(id: number) {
    const timer = timers.get(id);
    if (timer) clearTimeout(timer);
    timers.delete(id);
    setDeleted((prev) => { const next = new Set(prev); next.delete(id); return next; });
  }

  const today = new Date().toISOString().slice(0, 10);
  const switchEntries = entries.filter((e) => e.env_name !== null && !deleted.has(e.id));
  const projects = [...new Set(switchEntries.map((e) => e.project_name!))].sort();

  type EntryWithDuration = HistoryEntry & { durationMs: number | null; isActive: boolean };
  const withDuration: EntryWithDuration[] = [];
  const activeEntries = entries.filter((e) => !deleted.has(e.id));

  for (let i = 0; i < activeEntries.length; i++) {
    const entry = activeEntries[i];
    if (entry.env_name === null) continue;
    const start = new Date(entry.switched_at).getTime();
    const next = activeEntries[i + 1];
    let durationMs: number | null = null;
    let isActive = false;
    if (next) {
      durationMs = new Date(next.switched_at).getTime() - start;
    } else if (entry.switched_at.slice(0, 10) === today) {
      durationMs = now - start;
      isActive = true;
    }
    withDuration.push({ ...entry, durationMs, isActive });
  }

  const byDate: Record<string, EntryWithDuration[]> = {};
  for (const entry of withDuration) {
    const date = entry.switched_at.slice(0, 10);
    if (!byDate[date]) byDate[date] = [];
    byDate[date].push(entry);
  }
  const allDates = Object.keys(byDate).sort((a, b) => b.localeCompare(a));
  const totalPages = Math.max(1, Math.ceil(allDates.length / DAYS_PER_PAGE));
  const currentPage = Math.min(page, totalPages);
  const dates = allDates.slice((currentPage - 1) * DAYS_PER_PAGE, currentPage * DAYS_PER_PAGE);

  const totalSwitches = switchEntries.length;
  const flaggedCount = withDuration.filter((e) => !!e.flagged).length;

  if (switchEntries.length === 0) {
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
          onClick={() => router.push(`/history?days=${r}&page=1`)}
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
          <span className="section-label">history</span>
          {flaggedCount > 0 && (
            <>
              <span className="text-[10px] font-mono text-amber-500/70">{flaggedCount} flagged</span>
              <button
                onClick={clearFlags}
                disabled={clearingFlags}
                className="text-[10px] font-mono text-muted-foreground/60 hover:text-foreground border border-transparent hover:border-border rounded-[3px] px-1.5 py-0.5 transition-colors cursor-pointer disabled:opacity-50"
              >
                {clearingFlags ? "clearing…" : "clear flags"}
              </button>
            </>
          )}
        </div>
        <h1 className="text-5xl font-normal text-foreground tracking-tight leading-none">
          <span className="font-display font-bold tabular-nums">{totalSwitches}</span>
          <span className="text-muted-foreground/70 text-3xl font-normal ml-2">switches</span>
        </h1>
        <p className="text-sm text-muted-foreground/70 mt-2 tabular-nums">{allDates.length} days</p>
      </div>

      {/* Tick strip — divider between hero and content */}
      <div aria-hidden="true" className="ticks mb-8" />

      {/* Switch log */}
      <TermPanel title="switch log" right={rangeChips} bodyClassName="p-0">
        {dates.map((date, di) => {
          const dayEntries = byDate[date];
          const isToday = date === today;
          const totalMs = dayEntries.reduce((sum, e) => sum + (e.durationMs ?? 0), 0);
          const reversed = [...dayEntries].reverse();

          return (
            <div key={date} className={cn(di > 0 && "border-t border-border/60")}>
              <div className="flex items-center justify-between px-4 pt-4 pb-3">
                <div className="flex items-center gap-3">
                  <SectionHeader title={fmtDayHeader(date)} />
                  {isToday && <EnvTag label="today" variant="cyan" />}
                </div>
                {totalMs > 0 && (
                  <span className="text-[11px] text-muted-foreground/70 font-mono tabular-nums" suppressHydrationWarning>
                    {fmtDuration(totalMs)}
                  </span>
                )}
              </div>

              <div className="pb-2">
                {reversed.map((entry) => {
                  const isActive = entry.isActive;
                  return (
                    <div
                      key={entry.id}
                      className={cn(
                        "group flex items-center py-2.5 pl-3.5 pr-4 border-l-2 border-l-transparent border-b border-border/50 last:border-b-0 hover:border-l-cyan-400/60 transition-colors",
                        isActive && "bg-cyan-950/10 border-b-0 border-l-cyan-400/70"
                      )}
                    >
                      {/* Time */}
                      <Popover open={editingId === entry.id} onOpenChange={(open) => { if (!open) setEditingId(null); }}>
                        <PopoverTrigger
                          className="font-mono text-[11px] text-muted-foreground/70 w-11 shrink-0 cursor-pointer hover:text-muted-foreground transition-colors text-left tabular-nums"
                          suppressHydrationWarning
                          onClick={() => startEdit(entry)}
                        >
                          {fmtTime(entry.switched_at)}
                        </PopoverTrigger>
                        <PopoverContent className="w-64 p-3 bg-background border-border/50 flex flex-col gap-2" align="start">
                          <div className="flex items-center gap-2">
                            <input
                              type="time"
                              value={editTime}
                              autoFocus
                              className="font-mono text-sm text-foreground bg-muted border border-border rounded-[3px] px-2 py-1 outline-none focus:border-cyan-400/60 transition-colors"
                              onChange={(e) => setEditTime(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") saveEdit(entry);
                                if (e.key === "Escape") setEditingId(null);
                              }}
                            />
                            <button
                              className="w-6 h-6 flex items-center justify-center text-muted-foreground/60 hover:text-foreground/70 transition-colors cursor-pointer ml-auto"
                              onClick={() => saveEdit(entry)}
                            >
                              <CheckIcon className="w-3.5 h-3.5" />
                            </button>
                          </div>
                          <input
                            type="text"
                            value={editNote}
                            placeholder="note — what happened?"
                            className="font-mono text-xs text-foreground bg-muted border border-border rounded-[3px] px-2 py-1 outline-none focus:border-cyan-400/60 transition-colors w-full"
                            onChange={(e) => setEditNote(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") saveEdit(entry);
                              if (e.key === "Escape") setEditingId(null);
                            }}
                          />
                        </PopoverContent>
                      </Popover>

                      {/* Color dot */}
                      <span
                        className="w-1.5 h-1.5 rounded-full shrink-0 mx-3"
                        style={{
                          background: colorFor(entry.project_name!, projects),
                          boxShadow: isActive ? `0 0 6px 1px ${withAlpha(colorFor(entry.project_name!, projects), 27)}` : undefined,
                        }}
                      />

                      {/* Project + env */}
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <Link
                          href={`/projects?q=${encodeURIComponent(entry.project_name!)}`}
                          className="text-sm text-muted-foreground group-hover:text-foreground transition-colors font-mono truncate"
                        >
                          {entry.project_name}
                        </Link>
                        <span className="text-muted-foreground/60">/</span>
                        <Link
                          href={`/env/${entry.environment_id}`}
                          className="text-[11px] text-muted-foreground/70 font-mono hover:text-muted-foreground truncate transition-colors"
                        >
                          {entry.env_name}
                        </Link>
                        {entry.source === "manual" && <EnvTag label="manual" variant="cyan" />}
                        {entry.source !== "manual" && entry.edited && <EnvTag label="edited" variant="cyan" />}
                        {entry.note && (
                          <span className="text-[11px] text-muted-foreground/50 font-mono truncate italic" title={entry.note}>
                            — {entry.note}
                          </span>
                        )}
                      </div>

                      {/* Flagged */}
                      {!!entry.flagged && (
                        <EnvTag label="flagged" variant="violet" className="mr-2" />
                      )}

                      {/* Duration / active */}
                      <div className="ml-auto shrink-0 flex items-center gap-3">
                        {isActive ? (
                          <StatusIndicator ok={true} pulse size="md" label="active" className="text-[11px] text-cyan-500/70 font-mono" />
                        ) : entry.durationMs !== null ? (
                          <span className="text-[11px] text-muted-foreground/70 font-mono tabular-nums" suppressHydrationWarning>
                            {fmtDuration(entry.durationMs)}
                          </span>
                        ) : null}

                        {/* Actions */}
                        {isActive ? (
                          <button
                            onClick={stopTimesheet}
                            disabled={stopping}
                            title="Stop timesheet"
                            className="opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center text-muted-foreground/70 hover:text-amber-400 transition-all cursor-pointer"
                          >
                            <StopIcon className="w-3.5 h-3.5" />
                          </button>
                        ) : (
                          <button
                            onClick={() => deleteEntry(entry.id)}
                            title="Delete entry"
                            className="opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center text-muted-foreground/70 hover:text-red-400 transition-all cursor-pointer"
                          >
                            <TrashIcon className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </TermPanel>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-8">
          <Pagination>
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  href={currentPage > 1 ? pageHref(days, currentPage - 1) : undefined}
                  className={currentPage === 1 ? "pointer-events-none opacity-40" : ""}
                />
              </PaginationItem>
              {buildPageNumbers(currentPage, totalPages).map((p, i) =>
                p === "ellipsis" ? (
                  <PaginationItem key={`ellipsis-${i}`}>
                    <PaginationEllipsis />
                  </PaginationItem>
                ) : (
                  <PaginationItem key={p}>
                    <PaginationLink href={pageHref(days, p)} isActive={p === currentPage}>
                      {p}
                    </PaginationLink>
                  </PaginationItem>
                )
              )}
              <PaginationItem>
                <PaginationNext
                  href={currentPage < totalPages ? pageHref(days, currentPage + 1) : undefined}
                  className={currentPage === totalPages ? "pointer-events-none opacity-40" : ""}
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        </div>
      )}
    </div>
  );
}
