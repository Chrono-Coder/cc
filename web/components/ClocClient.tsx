"use client";

import { useState } from "react";
import { ArrowPathIcon, CodeBracketIcon } from "@heroicons/react/24/outline";
import { TermPanel } from "@/components/ui/term-panel";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

type Module = { id: number; name: string };
type ClocResult = { name: string; loc: number };

export default function ClocClient({
  envId,
  modules,
  initialData,
}: {
  envId: number;
  modules: Module[];
  initialData: { modules: ClocResult[]; total: number } | null;
}) {
  const [clocData, setClocData] = useState(initialData);
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">(initialData ? "done" : "idle");
  const [error, setError] = useState<string | null>(null);

  async function runCloc() {
    setState("loading");
    setError(null);
    try {
      const res = await fetch(`/api/env/${envId}/cloc`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed");
      setClocData(data);
      setState("done");
    } catch (e) {
      setError(String(e));
      setState("error");
    }
  }

  const modulesWithLoc = modules.map((m) => {
    const cloc = clocData?.modules.find((c) => c.name === m.name);
    return { ...m, loc: cloc?.loc ?? null };
  });
  const extraCloc = clocData?.modules.filter((c) => !modules.find((m) => m.name === c.name)) ?? [];
  const maxLoc = clocData ? Math.max(...clocData.modules.map((m) => m.loc), 1) : 1;

  return (
    <TermPanel
      title="cloc"
      right={
        <>
          {modules.length > 0 && (
            <span className="font-mono text-[10px] text-muted-foreground/60 tabular-nums">
              {modules.length} modules
            </span>
          )}
          <Tooltip>
            <TooltipTrigger render={
              <Button
                variant="ghost"
                size="sm"
                onClick={runCloc}
                disabled={state === "loading"}
                className="gap-1.5 text-muted-foreground/70 hover:text-muted-foreground cursor-pointer h-7 px-2"
              />
            }>
              {state === "loading" ? (
                <><ArrowPathIcon className="w-3 h-3 animate-spin" />Scanning...</>
              ) : (
                <><CodeBracketIcon className="w-3 h-3" />{state === "done" ? "Re-run" : "CLOC"}</>
              )}
            </TooltipTrigger>
            <TooltipContent>Count lines of code per module</TooltipContent>
          </Tooltip>
        </>
      }
      bodyClassName="px-4"
    >
      {error && (
        <p className="text-sm text-red-400 py-2">{error}</p>
      )}

      {(modulesWithLoc.length > 0 || extraCloc.length > 0) ? (
        <div>
          {modulesWithLoc.map((m) => {
            const pct = m.loc !== null ? Math.round((m.loc / maxLoc) * 100) : 0;
            return (
              <div key={m.id} className="relative flex items-center justify-between py-2.5 border-b border-border/50 last:border-0 overflow-hidden">
                {m.loc !== null && (
                  <div className="absolute inset-y-0 left-0 bg-cyan-500/5 transition-all duration-500" style={{ width: `${pct}%` }} />
                )}
                <span className="relative font-mono text-sm text-muted-foreground">{m.name}</span>
                <span className="relative font-mono text-sm tabular-nums">
                  {m.loc !== null ? (
                    <span className="text-cyan-500/70 font-medium">{m.loc.toLocaleString()}</span>
                  ) : state === "loading" ? (
                    <span className="text-muted-foreground/60">...</span>
                  ) : (
                    <span className="text-muted-foreground/70">--</span>
                  )}
                </span>
              </div>
            );
          })}
          {extraCloc.map((m) => {
            const pct = Math.round((m.loc / maxLoc) * 100);
            return (
              <div key={m.name} className="relative flex items-center justify-between py-2.5 border-b border-border/50 last:border-0 overflow-hidden">
                <div className="absolute inset-y-0 left-0 bg-violet-500/5 transition-all duration-500" style={{ width: `${pct}%` }} />
                <span className="relative font-mono text-sm text-muted-foreground/60">
                  {m.name}
                  <span className="ml-2 text-[10px] text-muted-foreground/60 uppercase tracking-wider">untracked</span>
                </span>
                <span className="relative font-mono text-sm tabular-nums text-violet-400/70 font-medium">{m.loc.toLocaleString()}</span>
              </div>
            );
          })}
          {clocData && (
            <div className="flex items-center justify-between py-3">
              <span className="font-mono text-[10px] text-muted-foreground/70 uppercase tracking-[0.3em]">total</span>
              <span className="font-mono text-sm font-semibold text-cyan-400 tabular-nums">{clocData.total.toLocaleString()}</span>
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground/60 py-4">No modules tracked. Run CLOC to discover.</p>
      )}
    </TermPanel>
  );
}
