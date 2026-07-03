import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

/**
 * The landing site's terminal-window panel, as a composable primitive:
 * hairline border, optional title-bar chrome (two edge dots + one hot),
 * mono title, optional right-side slot, optional scanlines body.
 */
export function TermPanel({
  title,
  right,
  scanlines = false,
  className,
  bodyClassName,
  children,
}: {
  title?: string;
  right?: ReactNode;
  scanlines?: boolean;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={cn(
        "overflow-hidden rounded-md border border-border bg-card/50",
        className,
      )}
    >
      {title !== undefined && (
        <div className="flex h-8 items-center gap-2 border-b border-border/60 px-4">
          <span aria-hidden className="size-[7px] rounded-full bg-border" />
          <span aria-hidden className="size-[7px] rounded-full bg-border" />
          <span aria-hidden className="size-[7px] rounded-full bg-hot/70" />
          <span className="ml-2 truncate font-mono text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
            {title}
          </span>
          {right && <span className="ml-auto flex items-center gap-2">{right}</span>}
        </div>
      )}
      <div className={cn("relative", scanlines && "scanlines", bodyClassName)}>
        {children}
      </div>
    </section>
  );
}
