import { Suspense } from "react";
import { api, type DbRecord } from "@/lib/api";
import DatabasesClient from "@/components/DatabasesClient";
import { Skeleton } from "@/components/ui/skeleton";

async function DatabasesContent() {
  let dbs: DbRecord[] = [];
  try {
    dbs = await api.databases();
  } catch { /* empty */ }
  return <DatabasesClient initialDbs={dbs} />;
}

function DatabasesSkeleton() {
  return (
    <div className="space-y-12">
      <div>
        <Skeleton className="h-3 w-24 mb-3" />
        <div className="flex items-end gap-12">
          <div className="space-y-3">
            <Skeleton className="h-10 w-16" />
            <Skeleton className="h-3 w-16" />
          </div>
          <div className="space-y-3">
            <Skeleton className="h-10 w-20" />
            <Skeleton className="h-3 w-20" />
          </div>
        </div>
      </div>
      <div className="rounded-lg border border-border/50 overflow-hidden">
        <div className="px-4 py-2 bg-muted/30 border-b border-border/50">
          <Skeleton className="h-4 w-full" />
        </div>
        {[...Array(8)].map((_, i) => (
          <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-border/50 last:border-0">
            <Skeleton className="h-4 w-48 shrink-0" />
            <Skeleton className="h-4 w-16 shrink-0" />
            <Skeleton className="h-4 w-20 shrink-0" />
            <Skeleton className="h-4 flex-1" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DatabasesPage() {
  return (
    <Suspense fallback={<DatabasesSkeleton />}>
      <DatabasesContent />
    </Suspense>
  );
}
