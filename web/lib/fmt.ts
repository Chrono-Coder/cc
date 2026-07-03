/**
 * Chart palette — CSS var()-based so every theme remaps it (chrono turns
 * cyan→yellow, light themes swap in darker variants). Never hardcode hex here.
 *
 * These strings work in inline `style=` and in SVG presentation attributes
 * (recharts `fill`/`stroke` — verified empirically: Chromium resolves var()
 * in presentation attributes). Do NOT concatenate hex alpha onto them
 * (``${color}44``) — use `withAlpha()` instead.
 */
export const PALETTE = [
  "var(--cc-cyan-400)", "var(--cc-violet-400)", "var(--cc-emerald-400)", "var(--cc-orange-400)",
  "var(--cc-rose-400)", "var(--cc-sky-400)", "var(--cc-fuchsia-400)", "var(--cc-amber-400)",
];

export function colorFor(project: string, projects: string[]): string {
  return PALETTE[projects.indexOf(project) % PALETTE.length];
}

/** Translucent version of a palette color — var()-safe (no hex-alpha concat). */
export function withAlpha(color: string, pct: number): string {
  return `color-mix(in oklch, ${color} ${pct}%, transparent)`;
}

export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function timeAgoNullable(iso: string | null): string {
  if (!iso) return "never";
  return timeAgo(iso);
}

/** ms → "1h 30m" */
export function fmtDuration(ms: number): string {
  const mins = Math.floor(ms / 60000);
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

/** minutes → "1h 30m" */
export function fmtHours(mins: number): string {
  const h = Math.floor(mins / 60);
  const m = Math.round(mins % 60);
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

/** bytes → "12.3 MB" */
export function fmtBytes(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)} MB`;
  return `${(bytes / 1073741824).toFixed(1)} GB`;
}

/** seconds → "2d 3h" or "3h 12m" or "12m" */
export function fmtUptime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d > 0) return `${d}d ${h % 24}h`;
  if (h > 0) return `${h}h ${m % 60}m`;
  return `${m}m`;
}

/** ISO string → "Mon 26" */
export function fmtDayHeader(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en", { weekday: "short", day: "numeric" });
}

/** ISO string → "14:30" */
export function fmtTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("en", { hour: "2-digit", minute: "2-digit", hour12: false });
}

/** ISO string or null → "today" / "3d ago" / "—" for last login */
export function fmtLogin(iso: string | null): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

/** ISO string → "May 26" */
export function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en", { month: "short", day: "numeric" });
}
