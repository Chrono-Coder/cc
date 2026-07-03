export type Environment = {
  id: number;
  name: string;
  branch_name: string | null;
  github_url: string | null;
  sh_url: string | null;
  last_used_at: string | null;
  database: string | null;
  version: string | null;
  is_active: boolean;
  pinned: boolean;
  status: string;
};

export type Project = {
  id: number;
  name: string;
  environments: Environment[];
  last_used: string | null;
};

export type Version = {
  id: number;
  name: string;
  path: string;
  port: string | null;
  branch: string | null;
  last_fetched_at: string | null;
};

export type Workspace = {
  id: number;
  name: string;
  workspace_path: string | null;
  is_rnd: number;
  version_id: number | null;
  version_name: string | null;
  version_path: string | null;
  port: string | null;
  branch: string | null;
  venv: string | null;
  last_fetched_at: string | null;
  project_count: number;
};

export type TimesheetEntry = {
  id: number;
  switched_at: string;
  flagged: boolean;
  env_name: string;
  project_name: string;
};

// Like TimesheetEntry but includes stop entries (env_name/project_name/environment_id are null for punch-outs)
export type HistoryEntry = {
  id: number;
  switched_at: string;
  flagged: boolean;
  environment_id: number | null;
  env_name: string | null;
  project_name: string | null;
  // 3.11 explicit-span fields
  ended_at: string | null;
  note: string | null;
  source: string | null;   // "auto" | "manual" (null = legacy auto)
  edited: boolean;
};

export type TimesheetSummary = {
  date: string;
  project: string;
  minutes: number;
  flagged: boolean;
};

export type HealthSeverity = "error" | "warning";

export type HealthIssue = {
  id: string;
  severity: HealthSeverity;
  title: string;
  description: string;
  items: string[];
  keys?: string[];
  droppable?: boolean;
};

export type DaemonHealth = {
  version?: string;
  uptime_seconds: number;
  rpc_count: number;
  last_error: string | null;
  db_size_bytes: number | null;
};

export type HealthReport = {
  issues: HealthIssue[];
  passed: string[];
  daemon?: DaemonHealth;
};

export type DbEnvLink = { name: string; project: string; is_active: boolean };

export type DbRecord = {
  id: number;
  name: string;
  size_bytes: number | null;
  last_login: string | null;
  is_odoo: boolean;
  in_pg: boolean;
  envs: DbEnvLink[];
};

export type GithubPR = {
  id: number;
  number: number;
  title: string;
  html_url: string;
  repo: string;
  author: string;
  author_avatar: string;
  created_at: string;
  updated_at: string;
  draft: boolean;
};

export type GithubReviews = {
  needs_review: GithubPR[];
  my_prs: GithubPR[];
};

// The ONE way to hit /api/* from anywhere (client or server component).
// Server components must not hand-roll fetch("http://localhost:3000/...") —
// that bypasses the 127.0.0.1/PORT base AND the auth token, so the proxy
// 401s the request.
export async function apiFetch<T>(path: string): Promise<T> {
  // Server-side (SSR) self-fetch: use 127.0.0.1 (IPv4) — `cc web` binds the
  // server to 127.0.0.1, and "localhost" resolves to ::1 first on macOS, which
  // hangs the request — and the real port from PORT (not a hardcoded 3000).
  const isServer = typeof window === "undefined";
  const base = isServer ? `http://127.0.0.1:${process.env.PORT ?? 3000}` : "";
  const headers: Record<string, string> = {};
  if (isServer) {
    // SSR self-fetches carry no browser cookie, so present the auth token
    // (see proxy.ts) as a Bearer header instead.
    try {
      const fs = await import("fs");
      const os = await import("os");
      const nodePath = await import("path");
      const token = fs
        .readFileSync(nodePath.join(os.homedir(), ".cc-cli", "web.token"), "utf8")
        .trim();
      if (token) headers.Authorization = `Bearer ${token}`;
    } catch {
      // no token file: auth disabled, nothing to attach
    }
  }
  const res = await fetch(`${base}${path}`, { cache: "no-store", headers });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  projects: () => apiFetch<Project[]>("/api/projects"),
  versions: () => apiFetch<Version[]>("/api/versions"),
  workspaces: () => apiFetch<Workspace[]>("/api/workspaces"),
  timesheet: (days = 30) => apiFetch<TimesheetEntry[]>(`/api/timesheet?days=${days}`),
  timesheetSummary: (days = 30) => apiFetch<TimesheetSummary[]>(`/api/timesheet/summary?days=${days}`),
  history: (days = 30) => apiFetch<HistoryEntry[]>(`/api/history?days=${days}`),
  githubReviews: () => apiFetch<GithubReviews>("/api/github/reviews"),
  health: () => apiFetch<HealthReport>("/api/health"),
  databases: () => apiFetch<DbRecord[]>("/api/databases"),
};
