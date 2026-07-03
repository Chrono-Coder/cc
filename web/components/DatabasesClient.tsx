"use client";

import { useState, useMemo, useRef } from "react";
import type { DbRecord } from "@/lib/api";
import {
  MagnifyingGlassIcon, TrashIcon, PencilIcon, CheckIcon, XMarkIcon,
  ExclamationTriangleIcon, ChevronUpIcon, ChevronDownIcon, ChevronUpDownIcon,
  AdjustmentsHorizontalIcon,
} from "@heroicons/react/24/outline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { TermPanel } from "@/components/ui/term-panel";
import { fmtBytes, fmtLogin } from "@/lib/fmt";

type ColWidths = { name: number; size: number; lastLogin: number };

function RenameField({ db, nameWidth, onRenamed }: { db: DbRecord; nameWidth: number; onRenamed: (newName: string) => void }) {
  const [value, setValue] = useState(db.name);
  const [state, setState] = useState<"idle" | "saving" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (value === db.name || !value.trim()) return;
    setState("saving");
    const res = await fetch("/api/databases/rename", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: db.id, old_name: db.name, new_name: value.trim() }),
    });
    const data = await res.json();
    if (res.ok) {
      onRenamed(value.trim());
    } else {
      setError(data.error ?? "Rename failed");
      setState("error");
    }
  }

  if (state === "error") return (
    <span className="text-xs text-red-400 truncate max-w-48" title={error ?? ""}>{error}</span>
  );

  return (
    <div className="flex items-center gap-1.5 min-w-0">
      <Input
        value={value}
        onChange={(e) => { setValue(e.target.value); setState("idle"); }}
        onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setValue(db.name); }}
        style={{ width: nameWidth - 48 }}
        className="h-6 text-xs font-mono px-1.5 bg-transparent border-border shrink-0"
        autoFocus
      />
      <Button variant="ghost" size="icon" onClick={save} disabled={state === "saving"} className="w-5 h-5 text-emerald-400 hover:text-emerald-300 hover:bg-transparent cursor-pointer shrink-0">
        <CheckIcon className="w-3 h-3" />
      </Button>
      <Button variant="ghost" size="icon" onClick={() => setValue(db.name)} className="w-5 h-5 text-muted-foreground hover:text-foreground hover:bg-transparent cursor-pointer shrink-0">
        <XMarkIcon className="w-3 h-3" />
      </Button>
    </div>
  );
}

function DropButton({ db, onDropped }: { db: DbRecord; onDropped: () => void }) {
  const [state, setState] = useState<"idle" | "confirming" | "dropping" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function drop() {
    setState("dropping");
    const res = await fetch("/api/databases/drop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: db.id, name: db.name }),
    });
    const data = await res.json();
    if (res.ok) {
      onDropped();
    } else {
      setError(data.error ?? "Drop failed");
      setState("error");
    }
  }

  if (state === "error") return (
    <span className="text-xs text-red-400 truncate max-w-32" title={error ?? ""}>{error}</span>
  );
  if (state === "dropping") return <span className="text-xs text-muted-foreground">dropping…</span>;
  if (state === "confirming") return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-amber-400">drop?</span>
      <Button variant="ghost" size="sm" onClick={drop} className="h-auto px-1.5 py-0.5 text-xs text-red-400 hover:text-red-300 hover:bg-transparent cursor-pointer">yes</Button>
      <Button variant="ghost" size="sm" onClick={() => setState("idle")} className="h-auto px-1.5 py-0.5 text-xs text-muted-foreground hover:bg-transparent cursor-pointer">no</Button>
    </div>
  );
  return (
    <Button variant="ghost" size="icon" onClick={() => setState("confirming")}
      className="opacity-0 group-hover:opacity-100 w-6 h-6 text-muted-foreground hover:text-red-400 hover:bg-transparent cursor-pointer shrink-0">
      <TrashIcon className="w-3.5 h-3.5" />
    </Button>
  );
}

function DbRow({ db: initial, colWidths, onRemoved }: { db: DbRecord; colWidths: ColWidths; onRemoved: () => void }) {
  const [db, setDb] = useState(initial);
  const [renaming, setRenaming] = useState(false);

  return (
    <div className="group flex items-center gap-4 px-4 py-3 border-b border-border border-l-2 border-l-transparent last:border-b-0 hover:bg-accent/30 hover:border-l-cyan-400/60 transition-colors">
      <div style={{ width: colWidths.name }} className="shrink-0 min-w-0">
        {renaming ? (
          <RenameField db={db} nameWidth={colWidths.name} onRenamed={(n) => { setDb({ ...db, name: n }); setRenaming(false); }} />
        ) : (
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="font-mono text-sm text-foreground truncate" title={db.name}>{db.name}</span>
            <Button variant="ghost" size="icon"
              onClick={() => setRenaming(true)}
              className="opacity-0 group-hover:opacity-100 w-5 h-5 text-muted-foreground hover:text-foreground hover:bg-transparent cursor-pointer shrink-0">
              <PencilIcon className="w-3 h-3" />
            </Button>
            {!db.in_pg && (
              <ExclamationTriangleIcon className="w-3.5 h-3.5 text-amber-400 shrink-0" title="Not found in PostgreSQL" />
            )}
          </div>
        )}
      </div>

      <div style={{ width: colWidths.size }} className="shrink-0 text-xs text-muted-foreground tabular-nums">
        {db.size_bytes != null ? fmtBytes(db.size_bytes) : "—"}
      </div>

      <div style={{ width: colWidths.lastLogin }} className="shrink-0 text-xs text-muted-foreground" suppressHydrationWarning>
        {db.is_odoo ? fmtLogin(db.last_login) : "—"}
      </div>

      <div className="flex flex-wrap gap-1.5 flex-1 min-w-0">
        {db.envs.length === 0 ? (
          <span className="text-xs text-muted-foreground/50 italic">unlinked</span>
        ) : (
          db.envs.map((e) => (
            <Badge key={`${e.project}-${e.name}`}
              className={`text-[11px] font-mono border gap-0.5 ${e.is_active ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/50" : "bg-muted/40 text-muted-foreground border-border"}`}>
              <span className="opacity-50">{e.project}/</span>{e.name}
            </Badge>
          ))
        )}
      </div>

      <div className="shrink-0 w-16 flex items-center justify-end gap-1">
        <DropButton db={db} onDropped={onRemoved} />
      </div>
    </div>
  );
}

type SortKey = "name" | "size" | "last_login";

function SortIcon({ col, sortKey, sortDir }: { col: SortKey; sortKey: SortKey | null; sortDir: "asc" | "desc" }) {
  if (sortKey !== col) return <ChevronUpDownIcon className="w-3 h-3 opacity-40" />;
  return sortDir === "asc"
    ? <ChevronUpIcon className="w-3 h-3 text-foreground" />
    : <ChevronDownIcon className="w-3 h-3 text-foreground" />;
}

const DEFAULT_WIDTHS: ColWidths = { name: 288, size: 64, lastLogin: 80 };
const MIN_WIDTHS: ColWidths = { name: 120, size: 48, lastLogin: 60 };

function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-[3px] bg-accent text-foreground text-xs font-medium px-1.5 py-0.5 shrink-0">
      {label}
      <button onClick={onRemove} className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer">
        <XMarkIcon className="w-2.5 h-2.5" />
      </button>
    </span>
  );
}

function FilterSection({
  label, items, value, onSelect, allLabel,
}: {
  label: string;
  items: string[];
  value: string;
  onSelect: (v: string) => void;
  allLabel: string;
}) {
  const [q, setQ] = useState("");
  const filtered = q ? items.filter((i) => i.toLowerCase().includes(q.toLowerCase())) : items;

  return (
    <div>
      <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-[0.3em] px-1 mb-1.5">{label}</p>
      {items.length > 6 && (
        <div className="relative mb-1">
          <MagnifyingGlassIcon className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={`Filter ${label.toLowerCase()}…`}
            className="w-full pl-6 pr-2 py-1 rounded-[3px] bg-muted/40 text-xs text-foreground placeholder:text-muted-foreground outline-none border border-transparent focus:border-cyan-400/60 transition-colors"
          />
        </div>
      )}
      <div className="space-y-0.5 max-h-52 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        {!q && (
          <button
            onClick={() => onSelect("all")}
            className={`flex items-center justify-between w-full px-2 py-1 rounded text-xs transition-colors cursor-pointer
              ${value === "all" ? "bg-accent text-foreground font-medium" : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"}`}
          >
            {allLabel}
            {value === "all" && <CheckIcon className="w-3 h-3" />}
          </button>
        )}
        {filtered.map((item) => (
          <button
            key={item}
            onClick={() => onSelect(item)}
            className={`flex items-center justify-between w-full px-2 py-1 rounded text-xs transition-colors cursor-pointer
              ${value === item ? "bg-accent text-foreground font-medium" : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"}`}
          >
            {item}
            {value === item && <CheckIcon className="w-3 h-3" />}
          </button>
        ))}
        {filtered.length === 0 && (
          <p className="px-2 py-1 text-xs text-muted-foreground/50 italic">No matches</p>
        )}
      </div>
    </div>
  );
}

function FilterPopover({
  projects, availableEnvs, projectFilter, envFilter, resolvedEnvFilter,
  onProjectChange, onEnvChange, onClear, activeCount,
}: {
  projects: string[];
  availableEnvs: string[];
  projectFilter: string;
  envFilter: string;
  resolvedEnvFilter: string;
  onProjectChange: (v: string) => void;
  onEnvChange: (v: string) => void;
  onClear: () => void;
  activeCount: number;
}) {
  return (
    <Popover>
      <PopoverTrigger className={`flex items-center gap-1.5 rounded-[3px] px-2 py-1 text-xs font-medium transition-colors cursor-pointer shrink-0
          ${activeCount > 0
            ? "bg-accent text-foreground"
            : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
          }`}>
        <AdjustmentsHorizontalIcon className="w-3.5 h-3.5" />
        Filters
        {activeCount > 0 && (
          <span className="flex items-center justify-center w-4 h-4 rounded-[3px] bg-foreground text-background text-[10px] font-bold leading-none">
            {activeCount}
          </span>
        )}
      </PopoverTrigger>
      <PopoverContent align="end" className="w-56 p-2 space-y-3">
        <FilterSection
          label="Project"
          items={projects}
          value={projectFilter}
          onSelect={onProjectChange}
          allLabel="All projects"
        />
        {availableEnvs.length > 0 && (
          <FilterSection
            label="Environment"
            items={availableEnvs}
            value={resolvedEnvFilter}
            onSelect={onEnvChange}
            allLabel="All envs"
          />
        )}
        {activeCount > 0 && (
          <button
            onClick={onClear}
            className="w-full text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer px-2 py-1 rounded hover:bg-accent/50 text-left"
          >
            Clear filters
          </button>
        )}
      </PopoverContent>
    </Popover>
  );
}

export default function DatabasesClient({ initialDbs }: { initialDbs: DbRecord[] }) {
  const [dbs, setDbs] = useState(initialDbs);
  const [search, setSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState("all");
  const [envFilter, setEnvFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [colWidths, setColWidths] = useState<ColWidths>(DEFAULT_WIDTHS);
  const inputRef = useRef<HTMLInputElement>(null);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  }

  function startResize(col: keyof ColWidths, e: React.MouseEvent) {
    e.preventDefault();
    const startX = e.clientX;
    const startW = colWidths[col];
    const min = MIN_WIDTHS[col];
    function onMove(ev: MouseEvent) {
      setColWidths((prev) => ({ ...prev, [col]: Math.max(min, startW + ev.clientX - startX) }));
    }
    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  const { projects, envsByProject } = useMemo(() => {
    const projectSet = new Set<string>();
    const envMap: Record<string, Set<string>> = {};
    for (const db of dbs) {
      for (const e of db.envs) {
        projectSet.add(e.project);
        if (!envMap[e.project]) envMap[e.project] = new Set();
        envMap[e.project].add(e.name);
      }
    }
    return { projects: Array.from(projectSet).sort(), envsByProject: envMap };
  }, [dbs]);

  const availableEnvs = useMemo(() => {
    if (projectFilter === "all") {
      const all = new Set<string>();
      Object.values(envsByProject).forEach((s) => s.forEach((e) => all.add(e)));
      return Array.from(all).sort();
    }
    return Array.from(envsByProject[projectFilter] ?? []).sort();
  }, [projectFilter, envsByProject]);

  const resolvedEnvFilter = availableEnvs.includes(envFilter) ? envFilter : "all";

  const activeFilterCount = (projectFilter !== "all" ? 1 : 0) + (resolvedEnvFilter !== "all" ? 1 : 0);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return dbs.filter((db) => {
      const matchesSearch = !q ||
        db.name.toLowerCase().includes(q) ||
        db.envs.some((e) => e.name.toLowerCase().includes(q) || e.project.toLowerCase().includes(q));
      const matchesProject = projectFilter === "all" || db.envs.some((e) => e.project === projectFilter);
      const matchesEnv = resolvedEnvFilter === "all" || db.envs.some((e) => e.name === resolvedEnvFilter);
      return matchesSearch && matchesProject && matchesEnv;
    });
  }, [dbs, search, projectFilter, resolvedEnvFilter]);

  const sorted = useMemo(() => {
    if (!sortKey) return filtered;
    return [...filtered].sort((a, b) => {
      let av: string | number, bv: string | number;
      if (sortKey === "name") { av = a.name.toLowerCase(); bv = b.name.toLowerCase(); }
      else if (sortKey === "size") { av = a.size_bytes ?? -1; bv = b.size_bytes ?? -1; }
      else { av = a.last_login ?? ""; bv = b.last_login ?? ""; }
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortDir]);

  const unlinked = dbs.filter((d) => d.envs.length === 0).length;
  const missingPg = dbs.filter((d) => !d.in_pg).length;
  const totalSize = dbs.reduce((s, d) => s + (d.size_bytes ?? 0), 0);

  return (
    <div className="">
      {/* Hero */}
      <div className="mb-4">
        <p className="section-label mb-1">databases</p>
        <div className="flex items-end justify-between flex-wrap gap-6">
          <div className="flex items-end gap-12">
            <div>
              <p className="text-4xl font-display font-bold text-foreground tabular-nums leading-none">{dbs.length}</p>
              <p className="text-xs text-muted-foreground mt-2">tracked</p>
            </div>
            <div>
              <p className="text-4xl font-normal text-foreground/70 tabular-nums leading-none">{fmtBytes(totalSize)}</p>
              <p className="text-xs text-muted-foreground mt-2">total size</p>
            </div>
            {unlinked > 0 && (
              <div>
                <p className="text-4xl font-normal text-amber-400/80 tabular-nums leading-none">{unlinked}</p>
                <p className="text-xs text-muted-foreground mt-2">unlinked</p>
              </div>
            )}
            {missingPg > 0 && (
              <div>
                <p className="text-4xl font-normal text-red-400/80 tabular-nums leading-none">{missingPg}</p>
                <p className="text-xs text-muted-foreground mt-2">missing in pg</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tick strip — divider between hero and content */}
      <div aria-hidden="true" className="ticks mb-8" />

      <div className="flex items-center justify-end mb-6">
        {/* Unified search + filter bar */}
        <div className="flex items-center gap-1.5 h-9 px-2.5 rounded-[3px] border border-input bg-background focus-within:border-cyan-400/60 transition-colors min-w-64">
          <MagnifyingGlassIcon className="w-3.5 h-3.5 text-muted-foreground shrink-0" />

          {/* Active filter chips */}
          {projectFilter !== "all" && (
            <FilterChip label={projectFilter} onRemove={() => { setProjectFilter("all"); setEnvFilter("all"); }} />
          )}
          {resolvedEnvFilter !== "all" && (
            <FilterChip label={resolvedEnvFilter} onRemove={() => setEnvFilter("all")} />
          )}

          <input
            ref={inputRef}
            placeholder={activeFilterCount === 0 ? "Search databases…" : ""}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Escape") { setSearch(""); setProjectFilter("all"); setEnvFilter("all"); } }}
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground min-w-0"
          />

          {(search || activeFilterCount > 0) && (
            <button
              onClick={(e) => { e.stopPropagation(); setSearch(""); setProjectFilter("all"); setEnvFilter("all"); }}
              className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer shrink-0"
            >
              <XMarkIcon className="w-3.5 h-3.5" />
            </button>
          )}

          <div className="w-px h-4 bg-border shrink-0" />

          <FilterPopover
            projects={projects}
            availableEnvs={availableEnvs}
            projectFilter={projectFilter}
            envFilter={envFilter}
            resolvedEnvFilter={resolvedEnvFilter}
            onProjectChange={(v) => { setProjectFilter(v); setEnvFilter("all"); }}
            onEnvChange={setEnvFilter}
            onClear={() => { setProjectFilter("all"); setEnvFilter("all"); }}
            activeCount={activeFilterCount}
          />
        </div>
      </div>

      <TermPanel
        title="databases"
        right={
          <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
            {sorted.length === dbs.length ? dbs.length : `${sorted.length}/${dbs.length}`}
          </span>
        }
      >
        <div className="flex items-center gap-4 px-4 py-2 bg-muted/30 border-b border-border border-l-2 border-l-transparent text-[10px] font-mono uppercase tracking-wider text-muted-foreground select-none">
          <div style={{ width: colWidths.name }} className="shrink-0 relative flex items-center">
            <button onClick={() => toggleSort("name")} className="flex items-center gap-1 hover:text-foreground transition-colors cursor-pointer">
              Name <SortIcon col="name" sortKey={sortKey} sortDir={sortDir} />
            </button>
            <div onMouseDown={(e) => startResize("name", e)} className="absolute right-0 top-0 h-full w-2 cursor-col-resize flex items-center justify-center group/handle">
              <div className="w-px h-3/5 bg-border group-hover/handle:bg-foreground/30 transition-colors" />
            </div>
          </div>

          <div style={{ width: colWidths.size }} className="shrink-0 relative flex items-center">
            <button onClick={() => toggleSort("size")} className="flex items-center gap-1 hover:text-foreground transition-colors cursor-pointer">
              Size <SortIcon col="size" sortKey={sortKey} sortDir={sortDir} />
            </button>
            <div onMouseDown={(e) => startResize("size", e)} className="absolute right-0 top-0 h-full w-2 cursor-col-resize flex items-center justify-center group/handle">
              <div className="w-px h-3/5 bg-border group-hover/handle:bg-foreground/30 transition-colors" />
            </div>
          </div>

          <div style={{ width: colWidths.lastLogin }} className="shrink-0 relative flex items-center">
            <button onClick={() => toggleSort("last_login")} className="flex items-center gap-1 hover:text-foreground transition-colors cursor-pointer">
              Last login <SortIcon col="last_login" sortKey={sortKey} sortDir={sortDir} />
            </button>
            <div onMouseDown={(e) => startResize("lastLogin", e)} className="absolute right-0 top-0 h-full w-2 cursor-col-resize flex items-center justify-center group/handle">
              <div className="w-px h-3/5 bg-border group-hover/handle:bg-foreground/30 transition-colors" />
            </div>
          </div>

          <span className="flex-1">Linked environments</span>
        </div>

        {sorted.length === 0 ? (
          <div className="px-4 py-10 text-center text-muted-foreground text-sm">No databases match your filter.</div>
        ) : (
          sorted.map((db) => (
            <DbRow
              key={db.id}
              db={db}
              colWidths={colWidths}
              onRemoved={() => setDbs((prev) => prev.filter((d) => d.id !== db.id))}
            />
          ))
        )}
      </TermPanel>
    </div>
  );
}
