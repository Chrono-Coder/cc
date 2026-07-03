import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { rpcCall } from "@/lib/rpc";

type PgDbStat = { datname: string; txns: number; stats_reset: string | null; size_bytes: number };

function fmtBytes(bytes: number): string {
  if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`;
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(0)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
}


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

export async function GET() {
  try {
    const db = getDb();
    const issues: HealthIssue[] = [];
    const passed: string[] = [];

    // 1. Projects with no environments
    const projectsNoEnvs = db.prepare(`
      SELECT p.name FROM project p
      LEFT JOIN environment e ON e.project_id = p.id
      WHERE e.id IS NULL
    `).all() as { name: string }[];
    if (projectsNoEnvs.length > 0) {
      issues.push({
        id: "project_no_envs",
        severity: "warning",
        title: "Projects with no environments",
        description: "These projects have no environments configured and can't be switched to.",
        items: projectsNoEnvs.map((p) => p.name),
      });
    } else {
      passed.push("All projects have at least one environment");
    }

    // 3–6. Single pass over all environments for field-missing and stale checks
    const cutoff = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString();
    const allEnvs = db.prepare(`
      SELECT
        e.id as env_id, e.name as env_name, p.name as project_name,
        e.branch_name, e.database_id, e.github_url, e.sh_url, e.last_used_at
      FROM environment e
      JOIN project p ON p.id = e.project_id
      WHERE (p.is_virtual = 0 OR p.is_virtual IS NULL)
      ORDER BY p.name, e.name
    `).all() as {
      env_id: number; env_name: string; project_name: string;
      branch_name: string | null; database_id: number | null;
      github_url: string | null; sh_url: string | null; last_used_at: string | null;
    }[];

    const envsNoBranch = allEnvs.filter((e) => !e.branch_name);
    if (envsNoBranch.length > 0) {
      issues.push({
        id: "env_no_branch",
        severity: "warning",
        title: "Environments missing a branch",
        description: "Branch checkout on switch won't work for these environments.",
        items: envsNoBranch.map((e) => `${e.project_name} / ${e.env_name}`),
      });
    } else {
      passed.push("All environments have a branch set");
    }

    const envsNoDb = allEnvs.filter((e) => !e.database_id);
    if (envsNoDb.length > 0) {
      const poolCountStmt = db.prepare(
        `SELECT COUNT(*) as cnt FROM database_environment_rel WHERE environment_id = ?`
      );
      const withPoolIds = new Set(
        envsNoDb
          .filter((e) => ((poolCountStmt.get(e.env_id) as { cnt: number }).cnt) > 0)
          .map((e) => e.env_id)
      );
      const envsWithPool = envsNoDb.filter((e) => withPoolIds.has(e.env_id));
      const envsWithoutPool = envsNoDb.filter((e) => !withPoolIds.has(e.env_id));

      if (envsWithPool.length > 0) {
        issues.push({
          id: "env_pool_no_active",
          severity: "warning",
          title: "Environments with a DB pool but no active database",
          description: "These environments have linked databases but none is set as active. Run cc db <name>.",
          items: envsWithPool.map((e) => `${e.project_name} / ${e.env_name}`),
        });
      }
      if (envsWithoutPool.length > 0) {
        issues.push({
          id: "env_no_database",
          severity: "warning",
          title: "Environments missing a database",
          description: "These environments have no database linked.",
          items: envsWithoutPool.map((e) => `${e.project_name} / ${e.env_name}`),
        });
      }
    } else {
      passed.push("All environments have a database linked");
    }

    const envsNoGithub = allEnvs.filter((e) => !e.github_url);
    if (envsNoGithub.length > 0) {
      issues.push({
        id: "env_no_github",
        severity: "warning",
        title: "Environments missing GitHub URL",
        description: "SH sync can't match these projects without a GitHub URL.",
        items: envsNoGithub.map((e) => `${e.project_name} / ${e.env_name}`),
      });
    } else {
      passed.push("All environments have a GitHub URL");
    }

    const envsNoSh = allEnvs.filter((e) => !e.sh_url);
    if (envsNoSh.length > 0) {
      issues.push({
        id: "env_no_sh_url",
        severity: "warning",
        title: "Environments without an SH URL",
        description: "cc sh won't work for these environments. Run Sync in Settings.",
        items: envsNoSh.map((e) => e.env_name),
      });
    } else {
      passed.push("All environments have an SH URL");
    }

    const staleEnvs = allEnvs.filter(
      (e) => e.last_used_at && e.last_used_at !== "0" && e.last_used_at < cutoff
    ).sort((a, b) => (a.last_used_at ?? "").localeCompare(b.last_used_at ?? ""));
    if (staleEnvs.length > 0) {
      const daysSince = (iso: string) => Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
      issues.push({
        id: "stale_envs",
        severity: "warning",
        title: "Stale environments",
        description: "These environments haven't been used in over 90 days. Consider removing them.",
        items: staleEnvs.map((e) => `${e.project_name} / ${e.env_name} — ${daysSince(e.last_used_at!)}d ago`),
      });
    }
    // (no "passed" message for this check — only surfaces when stale envs exist)

    // 0. Daemon health
    let daemon: DaemonHealth | undefined;
    try {
      daemon = await rpcCall("system.health") as DaemonHealth;
      if (daemon?.last_error) {
        issues.push({
          id: "daemon_last_error",
          severity: "warning",
          title: "Daemon last error",
          description: "The daemon encountered an unhandled error during its last RPC call.",
          items: [daemon.last_error],
        });
      }
    } catch {
      // daemon unavailable — skip
    }

    // 7. Postgres DB checks (orphaned in postgres / orphaned in cc)
    let pgDbs: string[] | null = null;
    let pgStats: PgDbStat[] = [];
    try {
      [pgDbs, pgStats] = await Promise.all([
        rpcCall("pg.list_databases") as Promise<string[]>,
        rpcCall("pg.get_db_stats") as Promise<PgDbStat[]>,
      ]);
    } catch {
      // daemon unavailable — skip Postgres checks
    }
    if (pgDbs !== null) {
      const ccDbs = db.prepare(`SELECT name FROM "database"`).all() as { name: string }[];
      const ccDbNames = new Set(ccDbs.map((d) => d.name));
      const pgDbNames = new Set(pgDbs);

      // Get stats (includes size) for all pg DBs
      const pgStatsMap = new Map(pgStats.map((s) => [s.datname, s]));

      // In postgres but not tracked in cc — sorted by size desc
      const orphanedInPg = pgDbs
        .filter((name) => !ccDbNames.has(name) && !name.includes("CC-COPY"))
        .sort((a, b) => (pgStatsMap.get(b)?.size_bytes ?? 0) - (pgStatsMap.get(a)?.size_bytes ?? 0));
      if (orphanedInPg.length > 0) {
        issues.push({
          id: "orphaned_postgres_dbs",
          severity: "warning",
          title: "Untracked PostgreSQL databases",
          description: "Exist in PostgreSQL but aren't linked to any CC environment. Sorted by size.",
          items: orphanedInPg.map((name) => {
            const stat = pgStatsMap.get(name);
            return stat ? `${name}  (${fmtBytes(stat.size_bytes)})` : name;
          }),
          keys: orphanedInPg,
          droppable: true,
        });
      } else {
        passed.push("No untracked PostgreSQL databases");
      }

      // In cc but not in postgres
      const orphanedInCc = ccDbs.filter((d) => !pgDbNames.has(d.name)).map((d) => d.name);
      if (orphanedInCc.length > 0) {
        issues.push({
          id: "missing_postgres_dbs",
          severity: "error",
          title: "CC databases missing from PostgreSQL",
          description: "These databases are tracked in CC but don't exist in PostgreSQL.",
          items: orphanedInCc,
        });
      } else {
        passed.push("All CC databases exist in PostgreSQL");
      }

      // Unused CC-tracked DBs — query res_users_log only for DBs that exist in both CC and postgres
      const cutoffDate = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000);
      const trackedInBoth = ccDbs.filter((d) => pgDbNames.has(d.name) && !d.name.includes("CC-COPY"));
      let lastLogins: Record<string, { last_login: string | null; is_odoo: boolean }> = {};
      try {
        if (trackedInBoth.length > 0) {
          lastLogins = await rpcCall("pg.get_last_logins", { db_names: trackedInBoth.map((d) => d.name) }) as Record<string, { last_login: string | null; is_odoo: boolean }>;
        }
      } catch { /* daemon may have died between calls — continue without login data */ }
      const unusedDbs = trackedInBoth
        .map(({ name }) => ({
          name,
          lastLogin: lastLogins[name]?.last_login ?? null,
          isOdoo: lastLogins[name]?.is_odoo ?? false,
          size_bytes: pgStatsMap.get(name)?.size_bytes ?? 0,
        }))
        .filter(({ isOdoo, lastLogin }) => isOdoo && (!lastLogin || new Date(lastLogin) < cutoffDate))
        .sort((a, b) => {
          if (!a.lastLogin && !b.lastLogin) return b.size_bytes - a.size_bytes;
          if (!a.lastLogin) return -1;
          if (!b.lastLogin) return 1;
          return new Date(a.lastLogin).getTime() - new Date(b.lastLogin).getTime();
        });
      if (unusedDbs.length > 0) {
        issues.push({
          id: "idle_postgres_dbs",
          severity: "warning",
          title: "Unused databases",
          description: "CC-tracked databases with no user logins in over 90 days. Based on res_users_log. Sorted by size.",
          items: unusedDbs.map(({ name, lastLogin, size_bytes }) => {
            const since = lastLogin
              ? ` · last login ${new Date(lastLogin).toLocaleDateString()}`
              : " · never logged in";
            return `${name}  (${fmtBytes(size_bytes)}${since})`;
          }),
          keys: unusedDbs.map(({ name }) => name),
          droppable: true,
        });
      } else {
        passed.push("No unused databases");
      }
    }

    // 10. Duplicate environment names within a project
    const dupEnvs = db.prepare(`
      SELECT p.name as project_name, e.name as env_name, COUNT(*) as cnt
      FROM environment e
      JOIN project p ON p.id = e.project_id
      GROUP BY e.project_id, e.name
      HAVING COUNT(*) > 1
      ORDER BY p.name, e.name
    `).all() as { project_name: string; env_name: string; cnt: number }[];
    if (dupEnvs.length > 0) {
      issues.push({
        id: "duplicate_env_names",
        severity: "error",
        title: "Duplicate environment names",
        description: "Multiple environments share the same name within a project.",
        items: dupEnvs.map((e) => `${e.project_name} / ${e.env_name} (×${e.cnt})`),
      });
    } else {
      passed.push("No duplicate environment names");
    }

    const result = { issues, passed, daemon } satisfies HealthReport;
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
