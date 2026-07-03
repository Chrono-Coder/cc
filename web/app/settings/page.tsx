"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { SectionHeader } from "@/components/ui/section-header";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { cn } from "@/lib/utils";

type Settings = Record<string, string | null>;

type SchemaEntry = {
  type: string;
  label: string;
  key?: string;
  description?: string;
  options?: Record<string, string>;
  default?: string;
};

/** Split the flat schema into groups by its "section" markers, dropping the
 *  theme entry (the companion has its own theme switcher in the sidebar). */
function buildGroups(schema: SchemaEntry[]): { title: string; fields: SchemaEntry[] }[] {
  const groups: { title: string; fields: SchemaEntry[] }[] = [];
  let current: { title: string; fields: SchemaEntry[] } | null = null;
  for (const entry of schema) {
    if (entry.type === "section") {
      current = { title: entry.label, fields: [] };
      groups.push(current);
    } else if (entry.type === "theme") {
      continue;
    } else if (entry.key) {
      if (!current) { current = { title: "General", fields: [] }; groups.push(current); }
      current.fields.push(entry);
    }
  }
  return groups.filter((g) => g.fields.length > 0);
}

// Shared control grammar — hairline borders, 3px radius, cyan focus edge
const inputCls =
  "w-full bg-background border border-border rounded-[3px] px-2.5 py-1.5 text-sm font-mono text-foreground/80 placeholder:text-muted-foreground/50 focus:outline-none focus:border-cyan-400/60 transition-colors";
const btnCls =
  "px-4 py-1.5 text-xs font-mono rounded-[3px] border border-border text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-default";
const btnPrimaryCls =
  "px-4 py-1.5 text-xs font-mono rounded-[3px] border border-cyan-500/60 bg-cyan-500/10 text-cyan-400 hover:bg-cyan-500/20 hover:border-cyan-400/80 hover:text-cyan-300 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-default";
const panelCls = "border border-border rounded-md bg-card/50 p-5";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({});
  const [schema, setSchema] = useState<SchemaEntry[]>([]);
  const [loaded, setLoaded] = useState(false);

  // Integration credentials state
  const [session, setSession] = useState("");
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [ghAuth, setGhAuth] = useState<{ authenticated: boolean; username: string | null } | null>(null);
  const [syncStatus, setSyncStatus] = useState<"idle" | "syncing" | "done" | "error">("idle");
  const [syncResult, setSyncResult] = useState<{ matched: number; unmatched: number; unmatched_envs: string[] } | null>(null);

  useEffect(() => {
    fetch("/api/settings").then((r) => r.json()).then((d) => {
      setSettings(d);
      setLoaded(true);
    });
    fetch("/api/settings/schema").then((r) => r.json()).then((d) => {
      if (Array.isArray(d)) setSchema(d);
    });
    fetch("/api/github/status").then((r) => r.json()).then(setGhAuth);
  }, []);

  async function saveCredential(body: Record<string, string>) {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return res.ok;
  }

  async function saveSh() {
    if (!session.trim()) return;
    setStatus("saving");
    const ok = await saveCredential({ sh_session_id: session.trim() });
    setStatus(ok ? "saved" : "error");
    if (ok) {
      setSettings((s) => ({ ...s, sh_session_id: "set" }));
      setSession("");
      setTimeout(() => setStatus("idle"), 2000);
    }
  }

  if (!loaded) return null;

  return (
    <div className="">
      {/* Hero */}
      <div className="mb-8">
        <p className="section-label mb-1">configuration</p>
        <h1 className="text-3xl font-normal text-foreground tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground mt-2">CC companion and CLI configuration</p>
      </div>

      <div aria-hidden="true" className="ticks mb-10" />

      {/* Integrations */}
      <section className="mb-14">
        <SectionHeader title="Integrations" className="mb-6" />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          {/* GitHub */}
          <div className={cn(panelCls, "space-y-5")}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono uppercase tracking-[0.2em] text-foreground/70">GitHub</span>
              <StatusIndicator ok={!!ghAuth?.authenticated} label={ghAuth?.authenticated ? "connected" : "not connected"} />
            </div>

            {ghAuth?.authenticated && ghAuth.username && (
              <p className="text-xs text-muted-foreground/60">Authenticated as <span className="font-mono text-muted-foreground">{ghAuth.username}</span> via <span className="font-mono text-muted-foreground">gh</span> CLI</p>
            )}

            {ghAuth && !ghAuth.authenticated && (
              <div className="border border-border/50 rounded-md p-4 bg-background/40">
                <p className="text-xs text-muted-foreground/60 leading-relaxed">
                  Run <span className="font-mono text-muted-foreground">gh auth login</span> in your terminal to connect GitHub.
                </p>
              </div>
            )}
          </div>

          {/* Odoo SH */}
          <div className={cn(panelCls, "space-y-5")}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono uppercase tracking-[0.2em] text-foreground/70">Odoo SH Session</span>
              <StatusIndicator ok={!!settings.sh_session_id} label={settings.sh_session_id ? "connected" : "not set"} />
            </div>

            <div className="flex items-center gap-3">
              <input
                type="password"
                value={session}
                onChange={(e) => setSession(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && saveSh()}
                placeholder="Paste session_id here..."
                className={cn(inputCls, "flex-1")}
              />
              <button
                onClick={saveSh}
                disabled={!session.trim() || status === "saving"}
                className={btnPrimaryCls}
              >
                {status === "saving" ? "saving…" : status === "saved" ? "saved" : "save"}
              </button>
            </div>
            {status === "error" && <p className="text-red-400 text-xs font-mono">Failed to save. Try again.</p>}

            {settings.sh_session_id && (
              <div className="border-t border-border/50 pt-5 space-y-3">
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-sm text-foreground/70">Sync SH Projects</p>
                    <p className="text-xs text-muted-foreground/60 mt-0.5">Match SH projects to CC environments via GitHub URL</p>
                  </div>
                  <button
                    onClick={async () => {
                      setSyncStatus("syncing");
                      const res = await fetch("/api/sh/sync", { method: "POST" });
                      const data = await res.json();
                      setSyncStatus(res.ok ? "done" : "error");
                      if (res.ok) setSyncResult({ matched: data.matched, unmatched: data.unmatched, unmatched_envs: data.unmatched_envs ?? [] });
                    }}
                    disabled={syncStatus === "syncing"}
                    className={btnCls}
                  >
                    {syncStatus === "syncing" ? "syncing…" : syncStatus === "done" ? "synced" : "sync now"}
                  </button>
                </div>
                {syncResult && (
                  <div className="space-y-2">
                    <p className="text-xs font-mono">
                      <span className="text-emerald-400/80">{syncResult.matched} matched</span>
                      {syncResult.unmatched > 0 && <span className="text-muted-foreground/60"> / {syncResult.unmatched} unmatched</span>}
                    </p>
                    {syncResult.unmatched_envs.length > 0 && (
                      <div className="max-h-28 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                        <p className="text-[10px] font-mono text-muted-foreground/70 uppercase tracking-wider mb-1">Unmatched</p>
                        {syncResult.unmatched_envs.map((e, i) => (
                          <p key={`${e}-${i}`} className="text-xs text-muted-foreground/60 font-mono py-0.5">{e}</p>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            <div className="border border-border/50 rounded-md p-4 bg-background/40">
              <ol className="text-xs text-muted-foreground/60 space-y-1 list-decimal list-inside">
                <li>Open <span className="font-mono text-muted-foreground">odoo.sh</span> and log in</li>
                <li>Press <span className="font-mono text-muted-foreground">F12</span> to open DevTools</li>
                <li>Go to <span className="font-mono text-muted-foreground">Application &rarr; Cookies &rarr; https://www.odoo.sh</span></li>
                <li>Copy the <span className="font-mono text-muted-foreground">session_id</span> value</li>
              </ol>
            </div>
          </div>
        </div>
      </section>

      {/* Configuration */}
      <section>
        <SectionHeader title="Configuration" className="mb-6" />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          {/* Rendered from cc.config.schema (via setting.schema) — the same
              source of truth the CLI uses, so the form never drifts. */}
          {buildGroups(schema).map((group) => (
            <SettingGroup key={group.title} title={group.title}>
              {group.fields.map((field) => (
                <SchemaField
                  key={field.key}
                  entry={field}
                  settings={settings}
                  onSaved={(v) => setSettings((s) => ({ ...s, [field.key as string]: v }))}
                />
              ))}
            </SettingGroup>
          ))}
        </div>
      </section>
    </div>
  );
}


// ---- Reusable setting components ----

function SchemaField({
  entry, settings, onSaved,
}: {
  entry: SchemaEntry;
  settings: Settings;
  onSaved: (v: string) => void;
}) {
  const key = entry.key as string;
  const common = {
    label: entry.label,
    description: entry.description ?? "",
    value: settings[key] ?? null,
    settingKey: key,
    onSaved,
  };
  if (entry.type === "bool") return <SettingToggle {...common} />;
  if (entry.type === "select") {
    const options = Object.entries(entry.options ?? {}).map(([label, value]) => ({ label, value }));
    return <SettingSelect {...common} options={options} />;
  }
  if (entry.type === "int") return <SettingInput {...common} type="number" placeholder={entry.default} />;
  return <SettingInput {...common} placeholder={entry.default} />;
}

function SettingGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className={cn(panelCls, "space-y-5")}>
      <span className="block text-xs font-mono uppercase tracking-[0.2em] text-foreground/70">{title}</span>
      <div className="space-y-5">
        {children}
      </div>
    </div>
  );
}

function SettingInput({
  label, description, value, settingKey, placeholder, type = "text", onSaved,
}: {
  label: string;
  description: string;
  value: string | null;
  settingKey: string;
  placeholder?: string;
  type?: string;
  onSaved: (v: string) => void;
}) {
  const [local, setLocal] = useState(value ?? "");
  const [saving, setSaving] = useState(false);

  useEffect(() => { setLocal(value ?? ""); }, [value]);

  const dirty = local !== (value ?? "");

  async function save() {
    if (!dirty) return;
    setSaving(true);
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [settingKey]: local }),
    });
    setSaving(false);
    if (res.ok) {
      onSaved(local);
      toast.success(`${label} saved`);
    } else {
      toast.error(`Couldn't save ${label}`);
    }
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <label className="text-xs font-mono text-muted-foreground">{label}</label>
        {dirty && (
          <button onClick={save} disabled={saving} className="text-[10px] font-mono text-cyan-400 hover:text-cyan-300 cursor-pointer transition-colors">
            {saving ? "saving…" : "save"}
          </button>
        )}
      </div>
      <p className="text-[11px] text-muted-foreground/70">{description}</p>
      <input
        type={type}
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && save()}
        placeholder={placeholder}
        className={inputCls}
      />
    </div>
  );
}

function SettingToggle({
  label, description, value, settingKey, onSaved,
}: {
  label: string;
  description: string;
  value: string | null;
  settingKey: string;
  onSaved: (v: string) => void;
}) {
  const isOn = value === "true";
  const [saving, setSaving] = useState(false);

  async function toggle() {
    const newVal = isOn ? "false" : "true";
    setSaving(true);
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [settingKey]: newVal }),
    });
    setSaving(false);
    if (res.ok) {
      onSaved(newVal);
      toast.success(`${label} ${newVal === "true" ? "enabled" : "disabled"}`);
    } else {
      toast.error(`Couldn't update ${label}`);
    }
  }

  return (
    <div className="flex items-center justify-between gap-4 py-1">
      <div className="min-w-0">
        <p className="text-xs font-mono text-muted-foreground">{label}</p>
        <p className="text-[11px] text-muted-foreground/70">{description}</p>
      </div>
      <button
        role="switch"
        aria-checked={isOn}
        onClick={toggle}
        disabled={saving}
        className={cn(
          "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-[3px] border transition-colors duration-200",
          isOn ? "border-cyan-400/60 bg-cyan-500/20" : "border-border bg-muted"
        )}
      >
        <span className={cn(
          "pointer-events-none inline-block h-3 w-3 mt-[3px] rounded-[2px] transform transition-all duration-200",
          isOn ? "translate-x-[19px] bg-cyan-400" : "translate-x-[3px] bg-muted-foreground/70"
        )} />
      </button>
    </div>
  );
}

function SettingSelect({
  label, description, value, options, settingKey, onSaved,
}: {
  label: string;
  description: string;
  value: string | null;
  options: { label: string; value: string }[];
  settingKey: string;
  onSaved: (v: string) => void;
}) {
  const [saving, setSaving] = useState(false);

  async function handleChange(newVal: string) {
    setSaving(true);
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [settingKey]: newVal }),
    });
    setSaving(false);
    if (res.ok) {
      onSaved(newVal);
      toast.success(`${label} saved`);
    } else {
      toast.error(`Couldn't save ${label}`);
    }
  }

  return (
    <div className="space-y-1">
      <label className="text-xs font-mono text-muted-foreground">{label}</label>
      <p className="text-[11px] text-muted-foreground/70">{description}</p>
      <select
        value={value ?? ""}
        onChange={(e) => handleChange(e.target.value)}
        disabled={saving}
        className={cn(inputCls, "cursor-pointer disabled:opacity-50")}
      >
        <option value="" disabled className="bg-background">Select...</option>
        {options.map((o) => (
          <option key={o.value} value={o.value} className="bg-background">{o.label}</option>
        ))}
      </select>
    </div>
  );
}
