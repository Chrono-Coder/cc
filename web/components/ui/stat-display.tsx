import { cn } from "@/lib/utils";

type StatDisplayProps = {
  label: string;
  value: string | number;
  accent?: boolean;
  className?: string;
};

export function StatDisplay({ label, value, accent, className }: StatDisplayProps) {
  return (
    <div className={cn("flex items-center justify-between gap-2", className)}>
      <span className="text-[10px] font-mono text-muted-foreground/70 uppercase tracking-[0.3em]">{label}</span>
      <span className={cn("font-display text-sm font-bold tabular-nums", accent ? "text-violet-400" : "text-muted-foreground")}>
        {value}
      </span>
    </div>
  );
}
