"use client";

import type { Project } from "@/lib/api";
import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import ProjectCard from "./ProjectCard";
import { MagnifyingGlassIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { SectionHeader } from "@/components/ui/section-header";

function sortByLastUsed(a: Project, b: Project) {
  if (!a.last_used && !b.last_used) return a.name.localeCompare(b.name);
  if (!a.last_used) return 1;
  if (!b.last_used) return -1;
  return b.last_used.localeCompare(a.last_used);
}

function filterProjects(projects: Project[], q: string) {
  if (!q.trim()) return projects;
  const lower = q.toLowerCase();
  return projects.filter(
    (p) =>
      p.name.toLowerCase().includes(lower) ||
      p.environments.some(
        (e) =>
          e.name.toLowerCase().includes(lower) ||
          e.branch_name?.toLowerCase().includes(lower)
      )
  );
}

export default function ProjectsGrid({
  active = [],
  inactive = [],
}: {
  active: Project[];
  inactive: Project[];
}) {
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");

  const filteredActive = useMemo(() => {
    const f = filterProjects(active, query);
    return query ? [...f].sort(sortByLastUsed) : f;
  }, [active, query]);

  const filteredInactive = useMemo(() => {
    const f = filterProjects(inactive, query);
    return query ? [...f].sort(sortByLastUsed) : f;
  }, [inactive, query]);

  const noResults = query.trim() !== "" && filteredActive.length === 0 && filteredInactive.length === 0;

  return (
    <div className="space-y-12">
      {/* Search */}
      <div className="relative">
        <MagnifyingGlassIcon className="absolute left-0 top-1/2 -translate-y-1/2 text-muted-foreground/70 w-4 h-4 pointer-events-none" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search projects, environments, branches..."
          className="w-full bg-transparent border-0 border-b border-border/50 pl-6 pr-8 py-3 text-sm text-foreground/70 placeholder:text-muted-foreground/60 focus:outline-none focus:border-border transition-colors"
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
        />
        {query && (
          <button
            onClick={() => setQuery("")}
            className="absolute right-0 top-1/2 -translate-y-1/2 text-muted-foreground/70 hover:text-muted-foreground transition-colors cursor-pointer"
          >
            <XMarkIcon className="w-4 h-4" />
          </button>
        )}
      </div>

      {noResults && (
        <p className="text-center text-muted-foreground/70 py-16 text-sm">No projects match &ldquo;{query}&rdquo;</p>
      )}

      {filteredActive.length > 0 && (
        <section className="space-y-6">
          <SectionHeader title="Active" />
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredActive.map((p) => (
              <ProjectCard key={p.id} project={p} />
            ))}
          </div>
        </section>
      )}

      {filteredInactive.length > 0 && (
        <section className="space-y-6">
          <SectionHeader title={filteredActive.length > 0 ? "Recent" : "Projects"} />
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredInactive.map((p) => (
              <ProjectCard key={p.id} project={p} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
