"use client";

import { useEffect, useRef, useState } from "react";
import { useIdle } from "@/hooks/useIdle";

const IDLE_MS = 10 * 60 * 1000;

// Chance of entering DVD mode when idle screen activates (1 in N)
const DVD_CHANCE = 6;

// Colors the bouncing logo cycles through on wall hits — theme tokens only,
// so chrono / light themes remap them.
const DVD_COLORS = [
  "var(--cc-cyan-400)",
  "var(--cc-violet-400)",
  "var(--cc-emerald-400)",
  "var(--cc-rose-400)",
  "var(--cc-amber-400)",
  "var(--cc-sky-400)",
  "var(--cc-fuchsia-400)",
] as const;

// CLI hints rotated on the idle screen
const HINTS: { cmd: string; desc: string }[] = [
  { cmd: "cc switch <env>",          desc: "jump between environments without leaving your terminal" },
  { cmd: "cc workspace add",         desc: "register a new Odoo install so cc can manage it" },
  { cmd: "cc backup create",         desc: "snapshot the active env's db (add -n for a custom name)" },
  { cmd: "cc backup restore",        desc: "roll the env's db back to a named backup" },
  { cmd: "cc copy",                  desc: "clone the active db to <db>-CC-COPY for safe experiments" },
  { cmd: "cc restore",               desc: "quick-restore the active db from its -CC-COPY snapshot" },
  { cmd: "cc db -p",                 desc: "narrow the db picker to only this env's pool" },
  { cmd: "cc db --link <db>",        desc: "add a database to the current env's pool" },
  { cmd: "cc stat",                  desc: "list all envs in the active project with versions and dbs" },
  { cmd: "cc pr",                    desc: "open the GitHub PR for your current branch" },
  { cmd: "cc sh",                    desc: "open an odoo.sh shell straight from the CLI" },
  { cmd: "cc theme",                 desc: "swap the cc color palette — chrono, sky, rose, sage…" },
  { cmd: "cc timesheet",             desc: "see how your hours break down across projects" },
  { cmd: "cc intel scan",            desc: "index your git history to power skill telemetry" },
  { cmd: "cc reindex",               desc: "rebuild the symbol index after big code changes" },
  { cmd: "cc sync push",             desc: "push state from this machine to the central server" },
  { cmd: "cc sync pull",             desc: "pull the latest state from your other machines" },
  { cmd: "cc cloc",                  desc: "count lines of code per Odoo module in the workspace" },
  { cmd: "cc psx",                   desc: "run quick postgres queries against the linked db" },
  { cmd: "cc setup",                 desc: "rerun the first-time wizard for any missing config" },
  { cmd: "cc venv",                  desc: "link or create a pyenv for the active version" },
  { cmd: "cc logs",                  desc: "tail the daemon log when something feels off" },
  { cmd: "cc daemon restart",        desc: "restart the daemon if the socket gets wedged" },
  { cmd: "cc module",                desc: "scaffold or upgrade modules in the active workspace" },
  { cmd: "cc ticket",                desc: "jump to the linked tickets for the current branch" },
  { cmd: "⌘K",                       desc: "quick switch envs from anywhere in the companion" },
  { cmd: "⌘B",                       desc: "collapse the sidebar to focus on the main view" },
  { cmd: "⌘E",                       desc: "open the notes editor for the current env" },
];

// The real `cc` banner — same art the CLI prints on a bare `cc`.
const BANNER_ART = ` ██████╗ ██████╗
██╔════╝██╔════╝
██║     ██║
██║     ██║
╚██████╗╚██████╗
 ╚═════╝ ╚═════╝`;

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Reduced motion ⇒ everything static, so the DVD bouncer never rolls.
function rollMode(): "normal" | "dvd" {
  if (prefersReducedMotion()) return "normal";
  return Math.floor(Math.random() * DVD_CHANCE) === 0 ? "dvd" : "normal";
}

export default function IdleScreen() {
  const idleAuto = useIdle(IDLE_MS);
  const [forced, setForced] = useState(false);
  const [now, setNow] = useState<Date | null>(null);
  const [idleSince, setIdleSince] = useState<number | null>(null);
  const [mode, setMode] = useState<"normal" | "dvd">("normal");
  const ignoreUntil = useRef(0);

  const visible = idleAuto || forced;

  // Trigger: Shift+I twice within 500ms, or window.dispatchEvent(new Event("cc:idle"))
  // Bonus: Shift+D twice forces DVD mode for testing
  useEffect(() => {
    let lastShiftI = 0;
    let lastShiftD = 0;
    function onKey(e: KeyboardEvent) {
      if (e.shiftKey && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const k = e.key.toLowerCase();
        if (k === "i") {
          const t = e.timeStamp;
          if (t - lastShiftI < 500) {
            e.preventDefault();
            ignoreUntil.current = Date.now() + 600;
            setMode(rollMode());
            setForced(true);
            lastShiftI = 0;
          } else {
            lastShiftI = t;
          }
        } else if (k === "d") {
          const t = e.timeStamp;
          if (t - lastShiftD < 500) {
            e.preventDefault();
            ignoreUntil.current = Date.now() + 600;
            setMode(prefersReducedMotion() ? "normal" : "dvd");
            setForced(true);
            lastShiftD = 0;
          } else {
            lastShiftD = t;
          }
        }
      }
    }
    function onTrigger() {
      ignoreUntil.current = Date.now() + 600;
      setMode(rollMode());
      setForced(true);
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener("cc:idle", onTrigger);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("cc:idle", onTrigger);
    };
  }, []);

  // Roll dice when auto-idle fires too
  useEffect(() => {
    if (idleAuto) setMode(rollMode());
  }, [idleAuto]);

  // Dismiss on click only — mousemove or keys never wake the screen
  useEffect(() => {
    if (!forced) return;
    function dismiss() {
      if (Date.now() < ignoreUntil.current) return;
      setForced(false);
    }
    const events = ["mousedown", "touchstart"] as const;
    for (const ev of events) window.addEventListener(ev, dismiss, { passive: true });
    return () => {
      for (const ev of events) window.removeEventListener(ev, dismiss);
    };
  }, [forced]);

  useEffect(() => {
    if (!visible) {
      setIdleSince(null);
      setNow(null);
      return;
    }
    setIdleSince(Date.now());
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, [visible]);

  if (!visible || !now) return null;

  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  const ss = String(now.getSeconds()).padStart(2, "0");
  const idleMinutes = idleSince ? Math.floor((Date.now() - idleSince) / 60000) : 0;

  return (
    <div
      className="idle-root fixed inset-0 z-[100] flex items-center justify-center bg-background animate-in fade-in duration-700 overflow-hidden"
      role="dialog"
      aria-modal="true"
      aria-label="cc idle screen — click to wake"
    >
      {/* Blueprint grid + phosphor pool */}
      <div className="idle-backdrop" aria-hidden />
      <div className="idle-glow" aria-hidden />

      {/* CRT scan sweep */}
      <div className="idle-scan" aria-hidden />

      {mode === "dvd" ? (
        <DvdBouncer />
      ) : (
        <>
          {/* Centerpiece — wordmark framed by tick strips */}
          <div className="relative flex flex-col items-center gap-7 mb-[14vh]">
            <div
              className="ticks w-[min(22rem,64vw)] [mask-image:linear-gradient(to_right,transparent,black_15%,black_85%,transparent)]"
              aria-hidden
            />
            {/* cursor overhangs absolutely so the banner alone defines center */}
            <div
              className="relative select-none text-[clamp(0.55rem,1.6vw,1.05rem)]"
              role="img"
              aria-label="cc"
            >
              <pre className="idle-wordmark phosphor whitespace-pre leading-[1.15] text-cyan-400 [font-family:var(--font-mono-full),var(--font-plex-mono),monospace]">
                {BANNER_ART}
              </pre>
              <span
                aria-hidden
                className="animate-blink absolute left-full top-0 ml-[0.6em] h-full w-[1.1em] bg-hot"
              />
            </div>
            <p className="font-mono text-[11px] uppercase tracking-[0.4em] text-muted-foreground/60">
              idle · {idleMinutes < 1 ? "just now" : `${idleMinutes}m`} — click to wake
            </p>
            <div
              className="ticks w-[min(22rem,64vw)] -scale-y-100 [mask-image:linear-gradient(to_right,transparent,black_15%,black_85%,transparent)]"
              aria-hidden
            />
          </div>

          {/* Lower third — clock + rotating CLI hint */}
          <div className="absolute inset-x-0 bottom-[8vh] flex flex-col items-center gap-8">
            {/* seconds overhang absolutely so HH:MM alone defines center */}
            <div className="relative">
              <span className="font-mono font-semibold tabular-nums text-foreground/85 leading-none text-[clamp(2rem,4vw,3rem)]">
                {hh}<span className="animate-blink">:</span>{mm}
              </span>
              <span className="absolute left-full bottom-0 ml-2 font-mono tabular-nums text-sm text-muted-foreground/50">
                {ss}
              </span>
            </div>
            <CommandHint />
          </div>
        </>
      )}

      {/* Frame hairlines */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyan-400/20 to-transparent" aria-hidden />
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyan-400/20 to-transparent" aria-hidden />
    </div>
  );
}

// ── Rotating CLI hint ───────────────────────────────────────────────────

function CommandHint() {
  const [idx, setIdx] = useState(() => Math.floor(Math.random() * HINTS.length));
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setIdx((i) => {
        let next = i;
        while (next === i) next = Math.floor(Math.random() * HINTS.length);
        return next;
      });
      setTick((t) => t + 1);
    }, 7000);
    return () => clearInterval(id);
  }, []);

  const hint = HINTS[idx];

  return (
    <div className="flex flex-col items-center gap-3 max-w-xl">
      <div className="flex items-center gap-3 w-full">
        <div className="flex-1 h-px bg-border/30" aria-hidden />
        <span className="section-label text-[10px]">tip</span>
        <div className="flex-1 h-px bg-border/30" aria-hidden />
      </div>
      <div key={tick} className="idle-hint flex flex-col items-center gap-1.5">
        <code className="font-mono text-base text-cyan-400/90">
          <span className="text-cyan-400/50 mr-2">›</span>{hint.cmd}
        </code>
        <p className="text-xs font-mono text-muted-foreground/70 text-center px-4">
          {hint.desc}
        </p>
      </div>
    </div>
  );
}

// ── DVD bouncer ─────────────────────────────────────────────────────────

function DvdBouncer() {
  const logoRef = useRef<HTMLDivElement>(null);
  const flashRef = useRef<HTMLDivElement>(null);
  const [cornerHits, setCornerHits] = useState(0);

  useEffect(() => {
    const el = logoRef.current;
    if (!el) return;

    let x = Math.random() * 200 + 50;
    let y = Math.random() * 200 + 50;
    let vx = 1.6 + Math.random() * 0.8;
    let vy = 1.2 + Math.random() * 0.8;
    if (Math.random() < 0.5) vx = -vx;
    if (Math.random() < 0.5) vy = -vy;

    let colorIdx = Math.floor(Math.random() * DVD_COLORS.length);
    el.style.color = DVD_COLORS[colorIdx];

    let raf = 0;
    let hits = 0;

    function tick() {
      if (!el) return;
      const w = el.offsetWidth;
      const h = el.offsetHeight;
      const maxX = window.innerWidth - w;
      const maxY = window.innerHeight - h;

      x += vx;
      y += vy;

      let hitX = false;
      let hitY = false;

      if (x <= 0) { x = 0; vx = Math.abs(vx); hitX = true; }
      else if (x >= maxX) { x = maxX; vx = -Math.abs(vx); hitX = true; }

      if (y <= 0) { y = 0; vy = Math.abs(vy); hitY = true; }
      else if (y >= maxY) { y = maxY; vy = -Math.abs(vy); hitY = true; }

      if (hitX || hitY) {
        colorIdx = (colorIdx + 1 + Math.floor(Math.random() * (DVD_COLORS.length - 1))) % DVD_COLORS.length;
        el.style.color = DVD_COLORS[colorIdx];
      }

      // CORNER HIT: both edges in the same frame
      if (hitX && hitY) {
        hits += 1;
        setCornerHits(hits);
        const flash = flashRef.current;
        if (flash) {
          flash.style.animation = "none";
          // Force reflow so animation restarts
          void flash.offsetHeight;
          flash.style.animation = "idle-corner-flash 0.8s ease-out";
        }
      }

      el.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      raf = requestAnimationFrame(tick);
    }

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <>
      {/* Bouncing logo — same block banner as the wordmark, color riding currentColor */}
      <div
        ref={logoRef}
        className="absolute top-0 left-0 flex items-stretch gap-[0.6em] select-none pointer-events-none will-change-transform"
        style={{
          fontSize: "clamp(0.45rem, 1.2vw, 0.8rem)",
          color: DVD_COLORS[0],
          textShadow: "0 0 30px currentColor, 0 0 80px color-mix(in srgb, currentColor 40%, transparent)",
          transition: "color 0.25s ease",
        }}
      >
        <pre className="whitespace-pre leading-[1.15] [font-family:var(--font-mono-full),var(--font-plex-mono),monospace]">
          {BANNER_ART}
        </pre>
        <span
          aria-hidden
          className="animate-blink inline-block w-[1.1em] self-stretch bg-current"
          style={{ boxShadow: "0 0 30px currentColor" }}
        />
      </div>

      {/* Corner-hit flash overlay */}
      <div
        ref={flashRef}
        className="absolute inset-0 pointer-events-none bg-foreground/10"
        style={{ opacity: 0 }}
        aria-hidden
      />

      {/* Corner hit counter */}
      {cornerHits > 0 && (
        <div className="absolute bottom-8 right-8 font-mono text-xs text-muted-foreground/60 tabular-nums pointer-events-none">
          corner hits · {cornerHits}
        </div>
      )}
    </>
  );
}
