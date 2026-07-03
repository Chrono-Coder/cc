export type TopTag = {
  tag: string;
  commit_count: number;
  repo_count: number;
  weight_total: number;
};

export type Subdomain = { tag: string; commits: number; repos: number };

export type Domain = {
  parent: string;
  commits: number;
  repos: number;
  subdomains: Subdomain[];
};

export type SkillsResponse = {
  total_commits: number;
  total_repos: number;
  top_tags: TopTag[];
  domains: Domain[];
  since: string | null;
  until: string | null;
};

export type Repo = {
  id: number;
  name: string;
  path: string;
  origin_url: string;
  enabled: boolean;
  last_indexed_commit_sha: string | null;
  last_indexed_at: string | null;
  skill_tag_count: number;
  knowledge_count: number;
};

export type SearchRow = {
  repository_id: number;
  repository_name: string;
  repository_path: string;
  origin_url: string;
  match: string;
  match_kind: string;
  commit_count: number;
  last_touched: string | null;
  top_files: string[];
  last_commit_sha: string | null;
};

export type RangePreset = "7d" | "30d" | "90d" | "1y" | "all";

export const RANGE_OPTIONS: { value: RangePreset; label: string }[] = [
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "1y", label: "Last year" },
  { value: "all", label: "Lifetime" },
];

export function rangeToISO(preset: RangePreset): { since: string | null; until: string | null } {
  if (preset === "all") return { since: null, until: null };
  const days = preset === "7d" ? 7 : preset === "30d" ? 30 : preset === "90d" ? 90 : 365;
  const since = new Date(Date.now() - days * 86400_000);
  return { since: since.toISOString().slice(0, 10), until: null };
}

export const TAG_LABELS: Record<string, string> = {
  model_override: "Model overrides", model_definition: "Custom models",
  wizard: "Wizards", compute_method: "Computed fields",
  constraint: "Constraints", controller: "HTTP controllers",
  controller_json: "JSON-RPC routes", controller_public: "Public routes",
  report: "Reports", owl_component: "OWL components",
  js_widget: "Legacy JS widgets", owl_template: "OWL templates",
  style: "Styles", js_test: "JS tests", tour_test: "Tour tests",
  assets_backend: "Backend UI", assets_frontend: "Public UI",
  assets_pos: "POS UI", assets_qweb: "QWeb assets",
  odoo_test: "Odoo tests", test: "Python tests",
  migration: "Migrations", migration_pre: "Pre-migrations",
  migration_post: "Post-migrations", migration_end: "End-migrations",
  performance: "Performance", security: "Security",
  cron_or_queue: "Crons / queues",
  odoo_external_api: "External APIs", external_api: "External APIs",
  cli: "CLI", db_query: "DB queries", concurrency: "Concurrency",
  dataclass: "Dataclasses", regex_heavy: "Regex parsing",
  config_ipc: "Config files", async_io: "Async I/O",
};

export function humanizeTag(t: string): string {
  if (TAG_LABELS[t]) return TAG_LABELS[t];
  if (t.startsWith("domain_")) {
    return t.slice(7).split("_").map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(" — ");
  }
  return t.replaceAll("_", " ").replace(/^./, c => c.toUpperCase());
}

export function humanizeDomain(parent: string): string {
  const rest = parent.slice(7);
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

export function originToHttp(origin: string): string | null {
  if (!origin) return null;
  const ssh = origin.match(/^git@([^:]+):(.+?)(?:\.git)?$/);
  if (ssh) return `https://${ssh[1]}/${ssh[2]}`;
  if (origin.startsWith("http")) return origin.replace(/\.git$/, "");
  return null;
}
