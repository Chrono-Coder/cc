"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import type { SearchRow } from "./types";
import { humanizeTag, originToHttp } from "./types";

export function SearchResultRow({ row: r }: { row: SearchRow }) {
  const [expanded, setExpanded] = useState(false);
  const hasFiles = r.top_files.length > 0;
  const repoUrl = originToHttp(r.origin_url);

  return (
    <div className="border-b last:border-b-0 py-2 text-sm">
      <div className="flex items-center justify-between">
        <div className="flex flex-col min-w-0">
          <span className="font-medium text-foreground truncate">
            {r.match_kind === "tag" ? humanizeTag(r.match) : r.match}
            <Badge variant="outline" className="ml-2 text-[10px] font-normal">{r.match_kind}</Badge>
          </span>
          <span className="text-xs truncate">
            {repoUrl ? (
              <a href={`${repoUrl}/commits`} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">{r.repository_name}</a>
            ) : (
              <span className="text-muted-foreground">{r.repository_name}</span>
            )}
            {hasFiles && (
              <button onClick={() => setExpanded(!expanded)} className="ml-1.5 text-muted-foreground hover:text-foreground cursor-pointer">
                {expanded ? "▾" : "▸"} {r.top_files.length} files
              </button>
            )}
            {r.last_touched && <span className="text-muted-foreground"> · last {r.last_touched.slice(0, 10)}</span>}
            {repoUrl && r.last_commit_sha && (
              <a href={`${repoUrl}/commit/${r.last_commit_sha}`} target="_blank" rel="noopener noreferrer" className="ml-1.5 text-primary/70 hover:text-primary hover:underline font-mono">
                {r.last_commit_sha.slice(0, 7)}
              </a>
            )}
          </span>
        </div>
        <div className="text-right tabular-nums shrink-0 ml-4">
          <div className="font-medium text-foreground">{r.commit_count} commits</div>
        </div>
      </div>
      {expanded && hasFiles && (
        <div className="mt-1.5 ml-1 pl-3 border-l border-border space-y-0.5">
          {r.top_files.map((f) =>
            repoUrl ? (
              <a key={f} href={`${repoUrl}/blob/HEAD/${f}`} target="_blank" rel="noopener noreferrer" className="block text-xs text-primary/80 hover:text-primary hover:underline truncate">{f}</a>
            ) : (
              <span key={f} className="block text-xs text-muted-foreground truncate">{f}</span>
            )
          )}
        </div>
      )}
    </div>
  );
}
