"use client";

import { useEffect, useMemo, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie,
} from "recharts";
import type { CSSProperties } from "react";
import { MagnifyingGlassIcon, CalendarIcon } from "@heroicons/react/24/outline";
import { useDebounce } from "@/hooks/useDebounce";
import { PALETTE } from "@/lib/fmt";
import { TermPanel } from "@/components/ui/term-panel";
import { cn } from "@/lib/utils";

import type { SkillsResponse, Repo, SearchRow, RangePreset } from "@/components/skills/types";
import { RANGE_OPTIONS, rangeToISO, humanizeTag, humanizeDomain } from "@/components/skills/types";
import { RepoFilter } from "@/components/skills/RepoFilter";
import { SearchResultRow } from "@/components/skills/SearchResultRow";

/* Chart chrome rides the theme tokens — never literal grays (chrono remaps cyan→yellow). */
const TOOLTIP_STYLE: CSSProperties = {
  background: "var(--popover)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  fontSize: 12,
  color: "var(--muted-foreground)",
};
const TOOLTIP_ITEM = { color: "var(--muted-foreground)" };
const AXIS_TICK = { fill: "var(--muted-foreground)", fillOpacity: 0.55 };

export default function SkillsClient() {
  const [range, setRange] = useState<RangePreset>("all");
  const [repoId, setRepoId] = useState<number | null>(null);
  const [data, setData] = useState<SkillsResponse | null>(null);
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(true);
  const [tagFilter, setTagFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchRow[] | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);

  const debouncedSearch = useDebounce(searchQuery, 250);

  useEffect(() => {
    fetch("/api/skills/repos").then(r => r.ok ? r.json() : []).then(setRepos).catch(() => setRepos([]));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    const { since, until } = rangeToISO(range);
    const qs = new URLSearchParams();
    if (since) qs.set("since", since);
    if (until) qs.set("until", until);
    if (repoId !== null) qs.set("repo_id", String(repoId));

    fetch(`/api/skills?${qs}`, { cache: "no-store", signal: controller.signal })
      .then(r => r.ok ? r.json() : null)
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { if (e.name !== "AbortError") { setData(null); setLoading(false); } });
    return () => controller.abort();
  }, [range, repoId]);

  useEffect(() => {
    if (!debouncedSearch.trim()) { setSearchResults(null); return; }
    const controller = new AbortController();
    setSearchLoading(true);
    const { since, until } = rangeToISO(range);
    const qs = new URLSearchParams({ q: debouncedSearch.trim(), limit: "10" });
    if (since) qs.set("since", since);
    if (until) qs.set("until", until);

    fetch(`/api/skills/search?${qs}`, { signal: controller.signal })
      .then(r => r.ok ? r.json() : [])
      .then(setSearchResults)
      .catch(e => { if (e.name !== "AbortError") setSearchResults([]); })
      .finally(() => setSearchLoading(false));
    return () => controller.abort();
  }, [debouncedSearch, range]);

  const filteredTags = useMemo(() => {
    if (!data) return [];
    const f = tagFilter.trim().toLowerCase();
    if (!f) return data.top_tags;
    return data.top_tags.filter(t => t.tag.toLowerCase().includes(f) || humanizeTag(t.tag).toLowerCase().includes(f));
  }, [data, tagFilter]);

  if (!loading && (!data || data.total_commits === 0)) {
    return (
      <div className="flex flex-col items-center justify-center py-40 text-center gap-3">
        <p className="font-mono text-muted-foreground text-lg">no indexed commits</p>
        <p className="text-muted-foreground/70 text-sm">
          Run <code className="text-foreground bg-muted px-1.5 py-0.5 rounded">cc intel scan</code>{" "}
          and <code className="text-foreground bg-muted px-1.5 py-0.5 rounded">cc reindex</code> to populate.
        </p>
      </div>
    );
  }

  const totalDomain = data?.domains.reduce((s, d) => s + d.commits, 0) ?? 0;
  const pieData = data?.domains.map((d, i) => ({ name: humanizeDomain(d.parent), value: d.commits, color: PALETTE[i % PALETTE.length] })) ?? [];

  return (
    <div>
      {/* Hero — stays outside the panels, landing grammar */}
      <div className="mb-4">
        <p className="section-label mb-1">skills</p>
        <div className="flex items-end gap-12">
          <div>
            {/* The page's one glow — hero commit count in dot-matrix */}
            <p className="font-display phosphor text-5xl font-semibold text-foreground tabular-nums leading-none">{data?.total_commits ?? "—"}</p>
            <p className="text-xs text-muted-foreground mt-2">commits</p>
          </div>
          <div>
            <p className="text-4xl font-normal text-foreground/70 tabular-nums leading-none">{data?.total_repos ?? "—"}</p>
            <p className="text-xs text-muted-foreground mt-2">repositories</p>
          </div>
          <div>
            <p className="text-4xl font-normal text-foreground/70 tabular-nums leading-none">{data?.top_tags.length ?? "—"}</p>
            <p className="text-xs text-muted-foreground mt-2">skills</p>
          </div>
        </div>
      </div>

      {/* Tick strip — divider between hero and content */}
      <div aria-hidden="true" className="ticks mb-8" />

      {/* Filters — page-wide controls, stay outside the panels */}
      <div className="flex flex-wrap items-center gap-4 mb-8">
        <div className="flex items-center gap-1">
          <CalendarIcon className="w-3.5 h-3.5 text-muted-foreground/70 mr-1" />
          {RANGE_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setRange(opt.value)}
              className={cn(
                "px-3 py-1 text-xs font-mono rounded-[3px] border transition-colors cursor-pointer",
                range === opt.value ? "text-cyan-300 border-cyan-400/40" : "text-muted-foreground/60 border-transparent hover:text-muted-foreground"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <RepoFilter repos={repos.filter(r => r.skill_tag_count > 0 || r.knowledge_count > 0)} repoId={repoId} setRepoId={setRepoId} />
        <div className="flex items-center gap-2 flex-1 min-w-50">
          <MagnifyingGlassIcon className="w-3.5 h-3.5 text-muted-foreground/70" />
          <input
            placeholder="Filter skills…"
            value={tagFilter}
            onChange={e => setTagFilter(e.target.value)}
            className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground/60 outline-none"
          />
        </div>
      </div>

      <div className="space-y-8">
        {/* Search */}
        <TermPanel title="did i ever work on…" bodyClassName="p-0">
          <div className={cn("flex items-center gap-2 px-4 py-1", searchQuery.trim() && "border-b border-border/40")}>
            <MagnifyingGlassIcon className="w-4 h-4 text-muted-foreground/70" />
            <input
              placeholder="Search models, files, or skills (e.g. account.move, payroll, wizard)…"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground/60 outline-none py-2"
            />
          </div>
          {searchQuery.trim() && (
            <div className="px-4 py-3">
              {searchLoading && <p className="text-muted-foreground text-sm">Searching…</p>}
              {!searchLoading && searchResults?.length === 0 && <p className="text-muted-foreground/70 text-sm">No matches.</p>}
              {!searchLoading && searchResults && searchResults.length > 0 && (
                <div className="space-y-1 max-h-96 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                  {searchResults.slice(0, 10).map((r, i) => <SearchResultRow key={`${r.repository_id}-${r.match}-${i}`} row={r} />)}
                </div>
              )}
            </div>
          )}
        </TermPanel>

        {/* Top skills bar chart */}
        <TermPanel title="top skills" bodyClassName="p-4">
          {filteredTags.length === 0 ? (
            <p className="text-muted-foreground/70 text-sm py-8 text-center">No skills match this filter.</p>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(280, filteredTags.length * 28)}>
              <BarChart data={filteredTags.map(t => ({ ...t, label: humanizeTag(t.tag) }))} layout="vertical" margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
                <XAxis type="number" tick={{ ...AXIS_TICK, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="label" tick={{ ...AXIS_TICK, fontSize: 12 }} width={170} axisLine={false} tickLine={false} />
                <Tooltip
                  cursor={{ fill: "var(--foreground)", fillOpacity: 0.04 }}
                  contentStyle={TOOLTIP_STYLE}
                  itemStyle={TOOLTIP_ITEM}
                  labelStyle={TOOLTIP_ITEM}
                  formatter={(value, _name, item) => {
                    const payload = (item as { payload?: { repo_count?: number } }).payload;
                    return [`${value} commits · ${payload?.repo_count ?? 0} repos`, ""];
                  }}
                />
                <Bar dataKey="commit_count" radius={[0, 4, 4, 0]}>
                  {filteredTags.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </TermPanel>

        {/* Domains */}
        {data && data.domains.length > 0 && (
          <TermPanel title="business domains" bodyClassName="p-4">
            <div className="grid md:grid-cols-2 gap-8">
              <div className="flex items-center justify-center">
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={2}>
                      {pieData.map((d, i) => <Cell key={i} fill={d.color} stroke="none" />)}
                    </Pie>
                    <Tooltip
                      contentStyle={TOOLTIP_STYLE}
                      itemStyle={TOOLTIP_ITEM}
                      labelStyle={TOOLTIP_ITEM}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-3">
                {data.domains.map((d, i) => {
                  const pct = totalDomain > 0 ? Math.round(100 * d.commits / totalDomain) : 0;
                  return (
                    <div key={d.parent}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm text-foreground">
                          <span className="inline-block w-2.5 h-2.5 rounded-full mr-2 align-middle" style={{ background: PALETTE[i % PALETTE.length] }} />
                          {humanizeDomain(d.parent)}
                        </span>
                        <span className="text-xs text-muted-foreground tabular-nums">{pct}% · {d.commits}</span>
                      </div>
                      <div className="h-1 bg-muted rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: PALETTE[i % PALETTE.length] }} />
                      </div>
                      {d.subdomains.length > 0 && (
                        <div className="mt-2 ml-4 flex flex-wrap gap-1.5">
                          {[...d.subdomains].sort((a, b) => b.commits - a.commits).map(s => (
                            <span key={s.tag} className="text-[10px] text-muted-foreground/70 font-mono">
                              {humanizeTag(s.tag).split(" — ").slice(-1)[0]}
                              <span className="ml-1 text-muted-foreground/50">{s.commits}</span>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </TermPanel>
        )}
      </div>
    </div>
  );
}
