import { Suspense } from "react";
import { api, type HealthReport } from "@/lib/api";
import HealthClient from "@/components/HealthClient";

async function HealthContent() {
  let report: HealthReport;
  try {
    report = await api.health();
  } catch {
    report = { issues: [], passed: [] };
  }
  return <HealthClient report={report} />;
}

function HealthSkeleton() {
  return (
    <div className="">
      <div className="mb-12">
        <div className="h-3 w-20 bg-muted rounded mb-3" />
        <div className="h-8 w-32 bg-muted rounded" />
      </div>
      <div className="flex items-center gap-8 py-4 border-b border-border/50">
        <div className="h-3 w-48 bg-muted rounded" />
      </div>
      <div className="mt-10 space-y-6">
        {[0, 1].map((i) => (
          <div key={i} className="space-y-3">
            <div className="h-4 w-40 bg-muted rounded" />
            <div className="h-3 w-64 bg-muted/60 rounded" />
            {[0, 1, 2].map((j) => (
              <div key={j} className="flex items-center gap-2 py-2 border-b border-border/50">
                <div className="w-1 h-1 rounded-full bg-accent" />
                <div className="h-3 flex-1 bg-muted/40 rounded" />
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function HealthPage() {
  return (
    <Suspense fallback={<HealthSkeleton />}>
      <HealthContent />
    </Suspense>
  );
}
