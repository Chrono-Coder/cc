type ActivityStripProps = {
  count?: number;
  bars?: number;
};

// Deterministic pseudo-random in [0,1) from an index — identical on server and
// client, so these decorative bars don't trip React hydration. (Math.random in
// the render path produced different values each side → hydration mismatch.)
function pseudo(i: number): number {
  const x = Math.sin((i + 1) * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

export function ActivityStrip({ count = 0, bars = 52 }: ActivityStripProps) {
  const cells = Array.from({ length: bars }, (_, i) => pseudo(i));

  return (
    <div className="text-right space-y-1">
      <div className="flex items-end gap-[2px] justify-end border-b border-border">
        {cells.map((v, i) => {
          const isCurrent = i === cells.length - 1;
          return (
            <div
              key={i}
              className="w-[3px] rounded-t-[1px]"
              style={{
                height: `${8 + v * 16}px`,
                background: isCurrent
                  ? "var(--cc-hot)"
                  : v > 0.7 ? "color-mix(in oklch, var(--cc-cyan-400) 60%, transparent)"
                  : v > 0.4 ? "color-mix(in oklch, var(--cc-cyan-400) 25%, transparent)"
                  : "color-mix(in oklch, var(--muted-foreground) 20%, transparent)",
                boxShadow: isCurrent
                  ? "0 0 6px color-mix(in oklch, var(--cc-hot) 50%, transparent)"
                  : undefined,
              }}
            />
          );
        })}
      </div>
      <p className="text-[10px] text-muted-foreground/70 font-mono">{count} switches today</p>
    </div>
  );
}
