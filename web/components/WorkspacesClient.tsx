"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import type { Workspace } from "@/lib/api";
import { StatDisplay } from "@/components/ui/stat-display";
import { EnvTag } from "@/components/ui/env-tag";
import { TermPanel } from "@/components/ui/term-panel";
import { timeAgoNullable } from "@/lib/fmt";
import { cn } from "@/lib/utils";

export type VersionOpt = { id: number; name: string };

const inputCls =
  "w-full bg-background border border-border rounded-[3px] px-2.5 py-1.5 text-sm font-mono text-foreground/80 placeholder:text-muted-foreground/50 focus:outline-none focus:border-cyan-400/60 transition-colors";
const linkBtn =
  "text-[10px] font-mono text-muted-foreground/60 hover:text-foreground transition-colors cursor-pointer disabled:opacity-50";

export default function WorkspacesClient({
  initialWorkspaces, versions,
}: {
  initialWorkspaces: Workspace[];
  versions: VersionOpt[];
}) {
  if (initialWorkspaces.length === 0) {
    return (
      <div>
        <div className="mb-4">
          <span className="section-label">infrastructure</span>
          <h1 className="text-3xl font-normal text-foreground tracking-tight">Workspaces</h1>
        </div>
        <div aria-hidden="true" className="ticks mb-8" />
        <div className="py-20 text-center">
          <p className="text-sm text-muted-foreground">no workspaces configured</p>
          <p className="text-xs text-muted-foreground/70 mt-2">
            Run <span className="font-mono text-muted-foreground">cc workspace create</span> or{" "}
            <span className="font-mono text-muted-foreground">cc config</span> to get started.
          </p>
        </div>
      </div>
    );
  }

  const rndCount = initialWorkspaces.filter((w) => w.is_rnd).length;
  const projectTotal = initialWorkspaces.reduce((s, w) => s + w.project_count, 0);

  return (
    <div>
      <div className="mb-4">
        <span className="section-label">infrastructure</span>
        <div className="flex items-end justify-between">
          <h1 className="text-3xl font-normal text-foreground tracking-tight">Workspaces</h1>
          <div className="flex items-center gap-6">
            <StatDisplay label="total" value={initialWorkspaces.length} />
            {rndCount > 0 && <StatDisplay label="R&D" value={rndCount} />}
            <StatDisplay label="projects" value={projectTotal} />
          </div>
        </div>
      </div>

      <div aria-hidden="true" className="ticks mb-8" />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {initialWorkspaces.map((w) => (
          <WorkspaceCard key={w.id} ws={w} versions={versions} />
        ))}
      </div>
    </div>
  );
}

function WorkspaceCard({
  ws, versions,
}: {
  ws: Workspace;
  versions: VersionOpt[];
}) {
  const router = useRouter();
  const [mode, setMode] = useState<"view" | "edit" | "confirmDelete">("view");
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState(ws.name);
  const [path, setPath] = useState(ws.workspace_path ?? "");
  const [isRnd, setIsRnd] = useState(Boolean(ws.is_rnd));
  const [versionId, setVersionId] = useState<number>(ws.version_id ?? 0);

  const displayPath = ws.version_path || ws.workspace_path;

  async function save() {
    setBusy(true);
    const res = await fetch(`/api/workspaces/${ws.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, path, is_rnd: isRnd, version_id: versionId }),
    });
    setBusy(false);
    if (res.ok) {
      toast.success(`${name} saved`);
      setMode("view");
      router.refresh();
    } else {
      toast.error("Couldn't save workspace");
    }
  }

  async function remove() {
    setBusy(true);
    const res = await fetch(`/api/workspaces/${ws.id}`, { method: "DELETE" });
    setBusy(false);
    if (res.ok) {
      toast.success(`${ws.name} deleted`);
      router.refresh();
    } else {
      toast.error("Couldn't delete workspace");
      setMode("view");
    }
  }

  return (
    <TermPanel
      title={ws.is_rnd ? `${ws.name} · r&d` : ws.name}
      right={ws.version_name ? <EnvTag label={ws.version_name} variant="zinc" className="text-[10px] px-2 py-0.5" /> : undefined}
      bodyClassName="p-4"
    >
      {mode === "edit" ? (
        <div className="space-y-3">
          <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="name" />
          <input className={inputCls} value={path} onChange={(e) => setPath(e.target.value)} placeholder="path (optional)" />
          <div className="flex items-center justify-between gap-4">
            <label className="flex items-center gap-2 text-xs font-mono text-muted-foreground cursor-pointer">
              <input type="checkbox" checked={isRnd} onChange={(e) => setIsRnd(e.target.checked)} className="accent-cyan-400" />
              R&amp;D workspace
            </label>
            <select
              className={cn(inputCls, "w-auto cursor-pointer")}
              value={versionId}
              onChange={(e) => setVersionId(Number(e.target.value))}
            >
              <option value={0} className="bg-background">no version</option>
              {versions.map((v) => (
                <option key={v.id} value={v.id} className="bg-background">{v.name}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-3 pt-1">
            <button onClick={save} disabled={busy} className="text-[10px] font-mono text-cyan-400 hover:text-cyan-300 cursor-pointer disabled:opacity-50">
              {busy ? "saving…" : "save"}
            </button>
            <button onClick={() => setMode("view")} disabled={busy} className={linkBtn}>cancel</button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {(ws.branch || ws.port) && (
            <div className="flex items-center gap-2 flex-wrap">
              {ws.branch && <EnvTag label={ws.branch} variant="violet" />}
              {ws.port && <EnvTag label={`:${ws.port}`} variant="cyan" />}
            </div>
          )}

          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground/70 tabular-nums">
              {ws.project_count > 0 ? `${ws.project_count} project${ws.project_count !== 1 ? "s" : ""}` : "—"}
            </span>
            <span className="text-[11px] text-muted-foreground/70 tabular-nums" suppressHydrationWarning>
              {timeAgoNullable(ws.last_fetched_at)}
            </span>
          </div>

          {ws.venv && ws.venv !== "skip" && (
            <div className="flex items-center gap-2 text-[11px]">
              <span className="font-mono uppercase tracking-wider text-muted-foreground/50">venv</span>
              <span className="font-mono text-muted-foreground/70 truncate" title={ws.venv}>{ws.venv}</span>
            </div>
          )}

          {displayPath && (
            <p className="font-mono text-[11px] text-muted-foreground/60 truncate border-t border-border/50 pt-3" title={displayPath}>
              {displayPath}
            </p>
          )}

          {/* actions */}
          <div className="flex items-center gap-4 border-t border-border/50 pt-3">
            <button onClick={() => setMode("edit")} className={linkBtn}>edit</button>
            {mode === "confirmDelete" ? (
              <span className="flex items-center gap-2 text-[10px] font-mono">
                <span className="text-muted-foreground/70">delete?</span>
                <button onClick={remove} disabled={busy} className="text-red-400 hover:text-red-300 cursor-pointer disabled:opacity-50">yes</button>
                <button onClick={() => setMode("view")} disabled={busy} className={linkBtn}>no</button>
              </span>
            ) : (
              <button onClick={() => setMode("confirmDelete")} className={cn(linkBtn, "hover:text-red-400")}>delete</button>
            )}
          </div>
        </div>
      )}
    </TermPanel>
  );
}
