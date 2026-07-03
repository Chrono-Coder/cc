import Link from "next/link";
import type { Project } from "@/lib/api";
import { TermPanel } from "@/components/ui/term-panel";
import { StatusBadge } from "@/components/ui/status-badge";
import { cn } from "@/lib/utils";

export default function ProjectCard({ project }: { project: Project }) {
  const hasActive = project.environments.some((e) => e.is_active);

  const sortedEnvs = [...project.environments].sort(
    (a, b) => Number(b.pinned) - Number(a.pinned) || Number(b.is_active) - Number(a.is_active)
  );

  return (
    <TermPanel
      title={project.name}
      right={
        <>
          <span className="font-mono text-[10px] text-muted-foreground">
            {project.environments.length} envs
          </span>
          {hasActive && (
            <span aria-hidden className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
          )}
        </>
      }
    >
      {sortedEnvs.length === 0 ? (
        <p className="px-4 py-2 font-mono text-xs text-muted-foreground/60">no environments</p>
      ) : (
        <ul className="divide-y divide-border/40">
          {sortedEnvs.map((env) => (
            <li key={env.id}>
              <Link
                href={`/env/${env.id}`}
                className="group/env relative flex items-center gap-2 px-4 py-2 before:absolute before:inset-y-0 before:left-0 before:w-0.5 before:bg-cyan-400 before:opacity-0 before:transition-opacity hover:before:opacity-100"
              >
                <span
                  aria-hidden
                  className={cn(
                    "size-1.5 shrink-0 rounded-full",
                    env.is_active ? "bg-emerald-400 animate-pulse" : "bg-border"
                  )}
                />
                <span className="min-w-0 truncate font-mono text-xs text-muted-foreground transition-colors group-hover/env:text-foreground">
                  {env.name}
                </span>
                {env.status && env.status !== "active" && (
                  <StatusBadge status={env.status} className="ml-auto shrink-0" />
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </TermPanel>
  );
}
