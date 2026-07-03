import { cn } from "@/lib/utils";

type EnvTagVariant = "zinc" | "violet" | "emerald" | "cyan";

type EnvTagProps = {
  label: string;
  variant?: EnvTagVariant;
  className?: string;
};

const variantStyles: Record<EnvTagVariant, string> = {
  zinc: "bg-muted text-muted-foreground border-border",
  violet: "bg-violet-950/30 text-violet-400/80 border-violet-900/30",
  emerald: "bg-emerald-950/30 text-emerald-400/80 border-emerald-900/30",
  cyan: "bg-cyan-950/30 text-cyan-400/80 border-cyan-900/30",
};

export function EnvTag({ label, variant = "zinc", className }: EnvTagProps) {
  return (
    <span className={cn("px-2.5 py-1 rounded-[3px] border text-xs font-mono", variantStyles[variant], className)}>
      {label}
    </span>
  );
}
