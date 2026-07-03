"use client";

import dynamic from "next/dynamic";
import { useState, useEffect, useCallback } from "react";
import type { Project } from "@/lib/api";
import { useEvents } from "@/hooks/useEvents";
import { StatDisplay } from "@/components/ui/stat-display";

const ProjectsGrid = dynamic(() => import("./ProjectsGrid"), { ssr: false });

function sortByLastUsed(a: Project, b: Project) {
  if (!a.last_used && !b.last_used) return a.name.localeCompare(b.name);
  if (!a.last_used) return 1;
  if (!b.last_used) return -1;
  return b.last_used.localeCompare(a.last_used);
}

export default function ProjectsGridClient({ initialProjects }: { initialProjects: Project[] }) {
  const [projects, setProjects] = useState<Project[]>(initialProjects);
  const [mounted, setMounted] = useState(false);
  const { subscribe } = useEvents();

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/projects", { cache: "no-store" });
      if (res.ok) setProjects(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    return subscribe("env.switched", () => refresh());
  }, [subscribe, refresh]);

  useEffect(() => { setMounted(true); }, []);

  const active = projects.filter((p) => p.environments.some((e) => e.is_active)).sort(sortByLastUsed);
  const inactive = projects.filter((p) => !p.environments.some((e) => e.is_active)).sort(sortByLastUsed);
  const envCount = projects.reduce((s, p) => s + p.environments.length, 0);

  return (
    <div className={` transition-opacity duration-700 ${mounted ? "opacity-100" : "opacity-0"}`}>
      {/* Header */}
      <div className="flex items-end justify-between mb-4">
        <div>
          <p className="section-label mb-1">projects</p>
          <h1 className="text-5xl font-normal text-foreground tracking-tight leading-none">
            <span className="font-display font-bold tabular-nums">{projects.length}</span>{" "}
            <span className="text-muted-foreground/60">projects</span>
          </h1>
        </div>
        <div className="flex items-end gap-8">
          <StatDisplay label="active" value={active.length} accent />
          <StatDisplay label="envs" value={envCount} />
        </div>
      </div>

      {/* Tick strip — divider between hero and content */}
      <div aria-hidden="true" className="ticks mb-8" />

      <ProjectsGrid active={active} inactive={inactive} />
    </div>
  );
}
