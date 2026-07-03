"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useTheme } from "@/components/ThemeProvider";
import { useEvents } from "@/hooks/useEvents";
import Link from "next/link";
import {
  HomeIcon,
  FolderIcon,
  ChartBarIcon,
  ClockIcon,
  ShieldCheckIcon,
  Cog6ToothIcon,
  CommandLineIcon,
  CircleStackIcon,
  AcademicCapIcon,
  RectangleStackIcon,
  MagnifyingGlassIcon,
  BookOpenIcon,
  ArrowTopRightOnSquareIcon,
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
} from "@heroicons/react/24/outline";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { CheckIcon, SwatchIcon } from "@heroicons/react/24/outline";
import { cn } from "@/lib/utils";

const COLLAPSE_KEY = "cc.sidebar.collapsed";

type NavItem = { href: string; label: string; icon: React.ReactNode };

const iconCls = "w-4 h-4 shrink-0";

const NAV: { label?: string; items: NavItem[] }[] = [
  {
    items: [
      { href: "/", label: "Home", icon: <HomeIcon className={iconCls} /> },
      { href: "/projects", label: "Projects", icon: <FolderIcon className={iconCls} /> },
      { href: "/workspaces", label: "Workspaces", icon: <RectangleStackIcon className={iconCls} /> },
    ],
  },
  {
    label: "Activity",
    items: [
      { href: "/timesheet", label: "Timesheet", icon: <ChartBarIcon className={iconCls} /> },
      { href: "/history", label: "History", icon: <ClockIcon className={iconCls} /> },
      { href: "/skills", label: "Skills", icon: <AcademicCapIcon className={iconCls} /> },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/databases", label: "Databases", icon: <CircleStackIcon className={iconCls} /> },
      { href: "/health", label: "Health", icon: <ShieldCheckIcon className={iconCls} /> },
      { href: "/logs", label: "Logs", icon: <CommandLineIcon className={iconCls} /> },
    ],
  },
];

export default function AppNav() {
  const pathname = usePathname();
  const [healthErrors, setHealthErrors] = useState(0);
  const [collapsed, setCollapsed] = useState(false);
  const [version, setVersion] = useState<string | null>(null);
  const { subscribe } = useEvents();
  const { theme, setTheme, themes } = useTheme();

  useEffect(() => {
    const stored = localStorage.getItem(COLLAPSE_KEY);
    if (stored === "1") setCollapsed(true);
  }, []);

  // the running daemon's version — never hardcoded
  useEffect(() => {
    fetch("/api/version")
      .then((r) => r.json())
      .then((d) => setVersion(d.version))
      .catch(() => {});
  }, []);

  function toggleCollapsed() {
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      return next;
    });
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "b") {
        e.preventDefault();
        toggleCollapsed();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch("/api/health", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        setHealthErrors(data.issues.length);
      }
    } catch {}
  }, []);

  useEffect(() => {
    fetchHealth();
    const unsub = subscribe("*", () => fetchHealth());
    return unsub;
  }, [fetchHealth, subscribe]);

  function isActive(href: string) {
    return href === "/" ? pathname === "/" : pathname.startsWith(href);
  }

  const currentTheme = themes.find((t) => t.value === theme);

  return (
    <nav
      className={cn(
        "sticky top-0 h-screen shrink-0 flex flex-col py-6 border-r border-border/30 transition-[width] duration-200 ease-out",
        collapsed ? "w-14 px-2" : "w-48 px-4"
      )}
    >
      {/* Logo + collapse */}
      <div className={cn("flex items-center mb-8", collapsed ? "justify-center" : "justify-between px-2")}>
        {!collapsed && (
          <Link href="/" className="flex items-baseline gap-0.5">
            <span className="text-sm font-mono font-semibold tracking-tight text-cyan-400">cc</span>
            <span aria-hidden className="animate-blink text-sm font-mono text-hot">▮</span>
            <span className="text-muted-foreground/60 text-xs font-normal">/companion</span>
          </Link>
        )}
        <button
          onClick={toggleCollapsed}
          title={`${collapsed ? "Expand" : "Collapse"} sidebar (⌘B)`}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="text-muted-foreground/60 hover:text-foreground transition-colors cursor-pointer p-1 rounded outline-none"
        >
          {collapsed
            ? <ChevronDoubleRightIcon className="w-3.5 h-3.5" />
            : <ChevronDoubleLeftIcon className="w-3.5 h-3.5" />
          }
        </button>
      </div>

      {/* Search trigger */}
      <button
        onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }))}
        className={cn(
          "flex items-center gap-2 py-1.5 mb-6 text-muted-foreground/50 hover:text-muted-foreground transition-colors outline-none cursor-pointer",
          collapsed ? "justify-center px-0" : "px-2"
        )}
        title="Quick search (⌘K)"
      >
        <MagnifyingGlassIcon className="w-3.5 h-3.5" />
        {!collapsed && (
          <>
            <span className="text-xs">Search</span>
            <kbd className="text-[9px] border border-border rounded-[2px] px-1 py-px ml-auto font-mono text-muted-foreground/60">⌘K</kbd>
          </>
        )}
      </button>

      {/* Nav groups */}
      <div className="flex-1 space-y-6">
        {NAV.map((group, gi) => (
          <div key={gi}>
            {group.label && !collapsed && (
              <p className="text-[9px] font-mono text-muted-foreground/50 uppercase tracking-[0.3em] px-2 mb-2">{group.label}</p>
            )}
            {group.label && collapsed && gi > 0 && (
              <div className="h-px bg-border/30 mx-2 mb-2" aria-hidden />
            )}
            <div className="space-y-0.5">
              {group.items.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  title={collapsed ? link.label : undefined}
                  className={cn(
                    "relative flex items-center rounded-md text-sm transition-colors focus-visible:outline-2",
                    collapsed ? "justify-center py-2" : "gap-2.5 px-2 py-1.5",
                    isActive(link.href)
                      ? "text-foreground bg-accent/40 before:absolute before:left-0 before:top-1 before:bottom-1 before:w-0.5 before:rounded-none before:bg-cyan-400"
                      : "text-muted-foreground hover:text-foreground hover:bg-accent/30"
                  )}
                >
                  {link.icon}
                  {!collapsed && <span>{link.label}</span>}
                  {!collapsed && link.href === "/health" && healthErrors > 0 && (
                    <span className="ml-auto text-[10px] font-mono text-amber-500/80">{healthErrors}</span>
                  )}
                  {collapsed && link.href === "/health" && healthErrors > 0 && (
                    <span className="absolute mt-3 ml-3 w-1.5 h-1.5 rounded-full bg-amber-500/80" aria-hidden />
                  )}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="space-y-1 pt-4 border-t border-border/20">
        {/* Settings */}
        <Link
          href="/settings"
          title={collapsed ? "Settings" : undefined}
          className={cn(
            "relative flex items-center rounded-md text-sm transition-colors focus-visible:outline-2",
            collapsed ? "justify-center py-2" : "gap-2.5 px-2 py-1.5",
            isActive("/settings")
              ? "text-foreground bg-accent/40 before:absolute before:left-0 before:top-1 before:bottom-1 before:w-0.5 before:rounded-none before:bg-cyan-400"
              : "text-muted-foreground hover:text-foreground hover:bg-accent/30"
          )}
        >
          <Cog6ToothIcon className={iconCls} />
          {!collapsed && <span>Settings</span>}
        </Link>

        {/* Docs */}
        <a
          href="https://cc.chronocoder.com/docs/commands"
          target="_blank"
          rel="noopener noreferrer"
          title={collapsed ? "Docs" : undefined}
          className={cn(
            "flex items-center rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-accent/30 transition-colors",
            collapsed ? "justify-center py-2" : "gap-2.5 px-2 py-1.5"
          )}
        >
          <BookOpenIcon className={iconCls} />
          {!collapsed && (
            <>
              <span>Docs</span>
              <ArrowTopRightOnSquareIcon className="w-3 h-3 ml-auto opacity-50" />
            </>
          )}
        </a>

        {/* Theme */}
        <Popover>
          <PopoverTrigger
            title={collapsed ? `Theme: ${currentTheme?.label}` : undefined}
            className={cn(
              "flex items-center w-full rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-accent/30 transition-colors cursor-pointer outline-none",
              collapsed ? "justify-center py-2" : "gap-2.5 px-2 py-1.5"
            )}
          >
            <span
              className="w-3 h-3 rounded-[2px] shrink-0 ring-1 ring-border/50"
              style={{ background: currentTheme?.color }}
            />
            {!collapsed && (
              <>
                <span>{currentTheme?.label}</span>
                <SwatchIcon className="w-3 h-3 ml-auto opacity-30" />
              </>
            )}
          </PopoverTrigger>
          <PopoverContent side="right" align="end" className="w-40 p-1">
            <p className="text-[9px] font-mono text-muted-foreground/50 uppercase tracking-[0.3em] px-2 py-1 mb-0.5">Theme</p>
            {themes.map((t) => (
              <button
                key={t.value}
                onClick={() => setTheme(t.value)}
                className="flex items-center gap-2 w-full px-2 py-1.5 rounded text-xs hover:bg-accent transition-colors cursor-pointer outline-none"
              >
                <span
                  className={cn(
                    "w-2.5 h-2.5 rounded-[2px] shrink-0 ring-1",
                    theme === t.value ? "ring-cyan-400/70" : "ring-border/50"
                  )}
                  style={{ background: t.color }}
                />
                <span className={theme === t.value ? "text-foreground font-medium" : "text-muted-foreground"}>
                  {t.label}
                </span>
                {theme === t.value && <CheckIcon className="w-3 h-3 ml-auto text-cyan-400" />}
              </button>
            ))}
          </PopoverContent>
        </Popover>

        {/* Version — served by the daemon via system.health */}
        {!collapsed && version && (
          <div className="px-2 pt-2">
            <span className="text-[9px] text-muted-foreground font-mono">v{version}</span>
          </div>
        )}
      </div>
    </nav>
  );
}
