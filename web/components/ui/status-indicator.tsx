import { cn } from "@/lib/utils";

type StatusIndicatorProps = {
  ok: boolean;
  label?: string;
  pulse?: boolean;
  size?: "sm" | "md";
  className?: string;
};

export function StatusIndicator({ ok, label, pulse, size = "sm", className }: StatusIndicatorProps) {
  const dotSize = size === "sm" ? "w-1.5 h-1.5" : "w-2 h-2";
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span
        className={cn(
          dotSize,
          "rounded-full",
          ok ? "bg-emerald-500/70" : "bg-red-400",
          ok && pulse && "animate-pulse",
          ok &&
            (pulse
              ? "shadow-[0_0_6px_1px_color-mix(in_oklch,var(--cc-emerald-400)_55%,transparent)]"
              : "shadow-sm shadow-emerald-400/30"),
        )}
      />
      {label && <span className="text-inherit">{label}</span>}
    </span>
  );
}
