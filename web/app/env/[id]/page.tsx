import { Suspense } from "react";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeftIcon } from "@heroicons/react/24/outline";
import EnvDetail, { type EnvData } from "@/components/EnvDetail";
import { TicketsClient, NotesClient } from "@/components/EnvSidebarClient";
import ClocClient from "@/components/ClocClient";
import { TermPanel } from "@/components/ui/term-panel";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api";

async function getEnv(id: string): Promise<EnvData | null> {
  try {
    // apiFetch, not a hand-rolled localhost fetch: it targets the real
    // host/port and carries the auth token the proxy requires.
    return await apiFetch<EnvData>(`/api/env/${id}`);
  } catch {
    return null;
  }
}

// ── CI Checks ────────────────────────────────────────────────────────────

function GitPRIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 16 16">
      <path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354Z" />
    </svg>
  );
}

function stateDot(state: string) {
  switch (state) {
    case "success": return true;
    case "failure": case "error": return false;
    case "pending": return true;
    default: return false;
  }
}

function stateLabel(state: string) {
  switch (state) {
    case "success": return "text-emerald-500/70";
    case "failure": case "error": return "text-red-400";
    case "pending": return "text-amber-500/70";
    default: return "text-muted-foreground/70";
  }
}

async function CIChecksSection({ envId, branch }: { envId: number; branch: string }) {
  let runs: { id: number; context: string; state: string; target_url: string | null }[] = [];
  let pr: { number: number; title: string; html_url: string; draft: boolean } | null = null;
  let error: string | null = null;

  try {
    const data = await apiFetch<{
      error?: string;
      runs: { id: number; context: string; state: string; target_url: string | null }[];
      pr?: { number: number; title: string; html_url: string; draft: boolean } | null;
    }>(`/api/env/${envId}/checks`);
    if (data.error) error = data.error;
    else { runs = data.runs; pr = data.pr ?? null; }
  } catch {
    error = "Failed to load checks";
  }

  if (!error && runs.length === 0 && !pr) return null;

  const anyFail = runs.some((r) => r.state === "failure" || r.state === "error");
  const anyPending = runs.some((r) => r.state === "pending");

  return (
    <TermPanel
      title={`ci · ${branch}`}
      right={<StatusIndicator ok={!error && !anyFail} pulse={anyPending} />}
      bodyClassName="px-4"
    >
      <div className="divide-y divide-border/50">
        {pr && (
          <a
            href={pr.html_url}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-center gap-3 py-2.5"
          >
            <GitPRIcon className="w-3.5 h-3.5 text-violet-400/80 shrink-0" />
            <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors flex-1 truncate font-mono">
              #{pr.number}
              <span className="ml-2 font-sans text-muted-foreground">{pr.title}</span>
            </span>
            {pr.draft && <span className="text-[10px] font-mono text-muted-foreground/70 uppercase tracking-wider">draft</span>}
          </a>
        )}
        {error ? (
          <p className="text-sm text-muted-foreground/70 py-2.5">{error}</p>
        ) : (
          runs.map((run) => (
            <a
              key={run.id}
              href={run.target_url ?? "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-center gap-3 py-2.5"
            >
              <StatusIndicator
                ok={stateDot(run.state)}
                pulse={run.state === "pending"}
              />
              <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors flex-1 truncate">
                {run.context}
              </span>
              <span className={`text-[10px] font-mono uppercase tracking-wider shrink-0 ${stateLabel(run.state)}`}>
                {run.state}
              </span>
            </a>
          ))
        )}
      </div>
    </TermPanel>
  );
}

function CIChecksSkeleton() {
  return (
    <TermPanel title="ci" bodyClassName="px-4">
      <div className="divide-y divide-border/50">
        {[0, 1].map((i) => (
          <div key={i} className="flex items-center gap-3 py-2.5">
            <Skeleton className="w-1.5 h-1.5 rounded-full shrink-0" />
            <Skeleton className="h-3 w-48" />
            <Skeleton className="ml-auto h-3 w-14 shrink-0" />
          </div>
        ))}
      </div>
    </TermPanel>
  );
}

// ── CLOC ────────────────────────────────────────────────────────────────

async function ClocSection({ envId, modules }: { envId: number; modules: EnvData["modules"] }) {
  let clocData: { modules: { name: string; loc: number }[]; total: number } | null = null;
  try {
    clocData = await apiFetch(`/api/env/${envId}/cloc`);
  } catch { /* show empty state */ }

  return <ClocClient envId={envId} modules={modules} initialData={clocData} />;
}

function ClocSkeleton({ moduleCount }: { moduleCount: number }) {
  const rows = Math.max(moduleCount, 3);
  return (
    <TermPanel
      title="cloc"
      right={<Skeleton className="h-5 w-20 rounded-md" />}
      bodyClassName="px-4"
    >
      <div className="divide-y divide-border/50">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center justify-between py-2.5">
            <Skeleton className="h-3 w-32" />
            <Skeleton className="h-3 w-12" />
          </div>
        ))}
      </div>
    </TermPanel>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────

export default async function EnvPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const env = await getEnv(id);
  if (!env) notFound();

  const hasCI = !!(env.github_url && env.branch_name);
  const isVirtual = env.is_virtual;

  return (
    <div className="">
      {/* Back link */}
      <Link
        href="/projects"
        className="inline-flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground/70 uppercase tracking-[0.3em] hover:text-muted-foreground transition-colors mb-10"
      >
        <ArrowLeftIcon className="w-3 h-3" />
        Projects
      </Link>

      {/* Hero — name, tags, links (stays outside panels) */}
      <EnvDetail env={env} />

      {/* Tick strip — divider between hero and panels */}
      <div aria-hidden="true" className="ticks mt-10 mb-8" />

      <div className="space-y-6">
        {/* Env meta + tickets */}
        <TermPanel title="environment" bodyClassName="px-4">
          <div className="divide-y divide-border/40">
            <div className="flex items-baseline gap-4 py-2.5">
              <span className="w-20 shrink-0 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground/60">project</span>
              <span className="font-mono text-sm text-muted-foreground truncate">{env.project.name}</span>
            </div>
            {!isVirtual && env.project_path && (
              <div className="flex items-baseline gap-4 py-2.5">
                <span className="w-20 shrink-0 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground/60">path</span>
                <span className="font-mono text-xs text-muted-foreground/70 break-all">{env.project_path}</span>
              </div>
            )}
            <div className="flex items-start gap-4 py-2.5">
              <span className="w-20 shrink-0 pt-1.5 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground/60">tickets</span>
              <TicketsClient envId={env.id} initialTickets={env.ticket_ids} />
            </div>
          </div>
        </TermPanel>

        {!isVirtual && hasCI && (
          <Suspense fallback={<CIChecksSkeleton />}>
            <CIChecksSection envId={env.id} branch={env.branch_name!} />
          </Suspense>
        )}

        {!isVirtual && (
          <Suspense fallback={<ClocSkeleton moduleCount={env.modules.length} />}>
            <ClocSection envId={env.id} modules={env.modules} />
          </Suspense>
        )}

        <NotesClient envId={env.id} initialNotes={env.notes} />
      </div>
    </div>
  );
}
