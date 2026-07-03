"use client";

import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { FolderOpenIcon } from "@heroicons/react/24/outline";
import { cn } from "@/lib/utils";
import type { Repo } from "./types";

type RepoFilterProps = {
  repos: Repo[];
  repoId: number | null;
  setRepoId: (id: number | null) => void;
};

export function RepoFilter({ repos, repoId, setRepoId }: RepoFilterProps) {
  const [search, setSearch] = useState("");
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return repos;
    return repos.filter(r => r.name.toLowerCase().includes(q));
  }, [repos, search]);

  return (
    <Popover>
      <PopoverTrigger className="inline-flex items-center gap-1.5 h-8 px-3 text-sm rounded-[3px] border border-input bg-background hover:bg-accent transition-colors cursor-pointer">
        <FolderOpenIcon className="w-4 h-4" />
        {repoId === null ? "All repos" : repos.find(r => r.id === repoId)?.name ?? "?"}
      </PopoverTrigger>
      <PopoverContent className="w-72 p-1" align="start" side="bottom">
        <div className="px-1 pb-1">
          <Input placeholder="Search repos…" value={search} onChange={e => setSearch(e.target.value)} className="h-7 text-xs" autoFocus />
        </div>
        <button onClick={() => setRepoId(null)} className={cn("w-full text-left px-2 py-1.5 text-sm rounded hover:bg-accent cursor-pointer", repoId === null && "bg-accent")}>
          All repos ({repos.length})
        </button>
        <div className="border-t my-1" />
        <div className="max-h-72 overflow-y-auto">
          {filtered.length === 0 && <p className="text-xs text-muted-foreground px-2 py-2">No repos match.</p>}
          {filtered.map(r => (
            <button key={r.id} onClick={() => setRepoId(r.id)} className={cn("w-full text-left px-2 py-1.5 text-sm rounded hover:bg-accent cursor-pointer", repoId === r.id && "bg-accent")}>
              <div className="font-medium truncate">{r.name}</div>
              <div className="text-xs text-muted-foreground tabular-nums">{r.skill_tag_count} tags · {r.knowledge_count} symbols</div>
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
