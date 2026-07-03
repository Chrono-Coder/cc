import { Suspense } from "react";
import LogsClient from "@/components/LogsClient";
import { apiFetch } from "@/lib/api";

type LogEntry = {
  timestamp: string;
  level: string;
  source: string;
  message: string;
};

async function LogsContent() {
  let logs: LogEntry[] = [];
  try {
    // apiFetch carries the auth token; a bare localhost fetch gets 401'd.
    logs = await apiFetch<LogEntry[]>("/api/logs?source=all&lines=200");
  } catch {
    /* first load may fail if no logs yet */
  }
  return <LogsClient initialLogs={logs} />;
}

function LogsSkeleton() {
  return (
    <div className="">
      <div className="mb-10">
        <div className="h-3 w-16 bg-muted rounded mb-3" />
        <div className="h-8 w-24 bg-muted rounded" />
      </div>
      <div className="flex gap-2 pb-6 border-b border-border/50">
        <div className="h-6 w-32 bg-muted/60 rounded" />
        <div className="h-6 w-56 bg-muted/60 rounded" />
      </div>
      <div className="space-y-0 mt-2">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className="flex gap-3 py-2 border-b border-border/30">
            <div className="h-3 w-[160px] bg-muted/40 rounded" />
            <div className="h-3 w-[40px] bg-muted/40 rounded" />
            <div className="h-3 flex-1 bg-muted/30 rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function LogsPage() {
  return (
    <Suspense fallback={<LogsSkeleton />}>
      <LogsContent />
    </Suspense>
  );
}
