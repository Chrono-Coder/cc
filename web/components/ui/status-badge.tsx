import { cn } from "@/lib/utils";

// Lifecycle status colors — theme tokens only (color-mix over --cc-* vars),
// so the chrono remap can't break them. Mirrors EnvDetail's status switcher.
const STATUS_STYLE: Record<string, string> = {
  active:
    "bg-emerald-950/40 text-emerald-400 shadow-[inset_0_0_12px_color-mix(in_oklch,var(--cc-emerald-400)_15%,transparent)]",
  merged:
    "bg-violet-950/40 text-violet-300 shadow-[inset_0_0_12px_color-mix(in_oklch,var(--cc-violet-400)_15%,transparent)]",
  archived: "bg-muted text-muted-foreground",
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const style = STATUS_STYLE[status] ?? STATUS_STYLE.archived;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[3px] px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wide",
        style,
        className,
      )}
    >
      {status}
    </span>
  );
}
