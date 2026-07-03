"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";

type Env = {
  id: number;
  name: string;
  project: string;
  branch: string | null;
  db: string | null;
  is_active: boolean;
  pinned: boolean;
  last_used_at: string | null;
};

function flattenEnvs(projects: any[]): Env[] {
  const envs: Env[] = [];
  for (const p of projects) {
    for (const e of p.environments ?? []) {
      envs.push({
        id: e.id,
        name: e.name,
        project: p.name,
        branch: e.branch_name ?? null,
        db: e.database ?? null,
        is_active: e.is_active ?? false,
        pinned: e.pinned ?? false,
        last_used_at: e.last_used_at ?? null,
      });
    }
  }
  // Sort: pinned first, then active, then by last_used_at descending
  envs.sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    if (a.is_active !== b.is_active) return a.is_active ? -1 : 1;
    if (!a.last_used_at && !b.last_used_at) return 0;
    if (!a.last_used_at) return 1;
    if (!b.last_used_at) return -1;
    return a.last_used_at < b.last_used_at ? 1 : -1;
  });
  return envs;
}

export default function QuickSwitcher() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [envs, setEnvs] = useState<Env[]>([]);
  const [cursor, setCursor] = useState(0);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Global Cmd+K / Ctrl+K listener
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Fetch envs when dialog opens
  useEffect(() => {
    if (!open) return;
    setQuery("");
    setCursor(0);
    fetch("/api/projects")
      .then((r) => r.json())
      .then((data) => setEnvs(flattenEnvs(data)))
      .catch(() => {});
  }, [open]);

  // Focus input when open
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  const filtered = envs.filter((e) => {
    const q = query.toLowerCase();
    return (
      e.name.toLowerCase().includes(q) ||
      e.project.toLowerCase().includes(q) ||
      (e.branch ?? "").toLowerCase().includes(q)
    );
  });

  // Keep cursor in bounds
  useEffect(() => {
    setCursor((c) => Math.min(c, Math.max(filtered.length - 1, 0)));
  }, [filtered.length]);

  // Scroll active item into view
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${cursor}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  const navigate = useCallback(
    (env: Env) => {
      setOpen(false);
      router.push(`/env/${env.id}`);
    },
    [router]
  );

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => (c + 1) % Math.max(filtered.length, 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => (c - 1 + Math.max(filtered.length, 1)) % Math.max(filtered.length, 1));
    } else if (e.key === "Enter" && filtered[cursor]) {
      navigate(filtered[cursor]);
    }
  }

  return (
    <>
      <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Backdrop className="fixed inset-0 z-50 bg-black/40" />
          <DialogPrimitive.Popup className="fixed top-[28%] left-1/2 z-50 w-full max-w-2xl -translate-x-1/2 overflow-hidden rounded-md bg-popover text-popover-foreground border border-border shadow-2xl outline-none">
          {/* Search input */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
            <span aria-hidden className="font-mono text-sm text-muted-foreground/40 select-none shrink-0">›</span>
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => { setQuery(e.target.value); setCursor(0); }}
              onKeyDown={onKeyDown}
              placeholder="search environments"
              className="flex-1 bg-transparent font-mono text-sm outline-none placeholder:text-muted-foreground/50 text-foreground"
            />
            <kbd className="text-[10px] text-muted-foreground/70 border border-border rounded-[2px] px-1 py-px font-mono">esc</kbd>
          </div>

          {/* Results */}
          <div ref={listRef} className="max-h-96 overflow-y-auto py-1.5 scrollbar-none [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
            {filtered.length === 0 && (
              <p className="text-center font-mono text-xs text-muted-foreground py-6">no environments found</p>
            )}
            {filtered.map((env, i) => (
              <button
                key={env.id}
                data-idx={i}
                onClick={() => navigate(env)}
                className={`w-full text-left flex items-center gap-3 px-4 py-2.5 text-sm border-l-2 transition-colors cursor-pointer ${
                  i === cursor
                    ? "border-l-cyan-400/80 bg-accent"
                    : "border-l-transparent hover:border-l-cyan-400/40 hover:bg-accent/50"
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`font-mono truncate ${i === cursor ? "text-foreground" : "text-muted-foreground"}`}>
                      {env.name}
                    </span>
                    {env.pinned && <span className="text-amber-400 text-xs leading-none shrink-0">★</span>}
                    {env.is_active && (
                      <span className="text-[10px] text-emerald-400/70 leading-none shrink-0">
                        active
                      </span>
                    )}
                  </div>
                  <div className="text-sm truncate mt-0.5">
                    <span className="text-muted-foreground">{env.project}</span>
                    {env.branch && <><span className="text-muted-foreground/60"> · </span><span className="text-violet-400/70 font-mono text-xs">{env.branch}</span></>}
                    {env.db && <><span className="text-muted-foreground/60"> · </span><span className="text-emerald-400/70 font-mono text-xs">{env.db}</span></>}
                  </div>
                </div>
                {i === cursor && (
                  <kbd className="text-[10px] text-muted-foreground/70 font-mono border border-border rounded-[2px] px-1 py-px shrink-0">↵</kbd>
                )}
              </button>
            ))}
          </div>

          {/* Footer hint */}
          {filtered.length > 0 && (
            <div className="px-4 py-2 border-t border-border flex gap-4 font-mono text-[10px] text-muted-foreground/70">
              <span><kbd className="text-muted-foreground/60 border border-border rounded-[2px] px-1 py-px">↑↓</kbd> navigate</span>
              <span><kbd className="text-muted-foreground/60 border border-border rounded-[2px] px-1 py-px">↵</kbd> open</span>
              <span><kbd className="text-muted-foreground/60 border border-border rounded-[2px] px-1 py-px">esc</kbd> close</span>
            </div>
          )}
          </DialogPrimitive.Popup>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>
    </>
  );
}
