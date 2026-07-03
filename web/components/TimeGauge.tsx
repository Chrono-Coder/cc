import { withAlpha } from "@/lib/fmt";

type TimeGaugeEntry = {
  project: string;
  minutes: number;
  color: string;
};

type TimeGaugeProps = {
  entries: TimeGaugeEntry[];
  total: string;
  maxHours?: number;
};

const RADIUS = 54;
const STROKE = 6;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function TimeGauge({ entries, total, maxHours = 8 }: TimeGaugeProps) {
  const maxMins = maxHours * 60;

  let cumulative = 0;
  const segments = entries.map((e) => {
    const start = cumulative / maxMins;
    cumulative += e.minutes;
    const end = cumulative / maxMins;
    return { ...e, start, end };
  });

  return (
    <div className="relative w-40 h-40">
      <svg viewBox="0 0 128 128" className="w-full h-full -rotate-90">
        <circle
          cx="64" cy="64" r={RADIUS}
          fill="none"
          strokeWidth={STROKE}
          style={{ stroke: "color-mix(in oklch, var(--muted-foreground) 20%, transparent)" }}
        />
        {segments.map((seg, i) => (
          <circle
            key={i}
            cx="64" cy="64" r={RADIUS}
            fill="none"
            stroke={seg.color}
            strokeWidth={STROKE}
            strokeDasharray={`${(seg.end - seg.start) * CIRCUMFERENCE} ${CIRCUMFERENCE}`}
            strokeDashoffset={-seg.start * CIRCUMFERENCE}
            strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 4px ${withAlpha(seg.color, 25)})` }}
          />
        ))}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display font-bold phosphor text-2xl text-foreground tabular-nums tracking-tight">{total}</span>
        <span className="text-[10px] text-muted-foreground/60 font-mono uppercase tracking-widest mt-0.5">today</span>
      </div>
    </div>
  );
}
