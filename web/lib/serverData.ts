// Server-only data reads, shared by API routes AND server components. Server
// components must NOT fetch their own /api routes during render (that self-fetch
// deadlocks under `next start`) — they call these directly instead.
import { getDb } from "@/lib/db";
import type { Project } from "@/lib/api";

export function getProjects(): Project[] {
  const db = getDb();
  const rows = db.prepare(`
    SELECT
      p.id, p.name,
      e.id as env_id, e.name as env_name, e.branch_name, e.github_url, e.sh_url, e.last_used_at, e.pinned, e.status,
      d.name as database_name,
      v.name as version_name,
      CASE WHEN a.environment_id IS NOT NULL THEN 1 ELSE 0 END as is_active,
      pl.last_used
    FROM project p
    LEFT JOIN environment e ON e.project_id = p.id
    LEFT JOIN "database" d ON d.id = e.database_id
    LEFT JOIN version v ON v.id = e.version_id
    LEFT JOIN app_state a ON a.environment_id = e.id
    LEFT JOIN (
      SELECT se.project_id, MAX(sl.switched_at) as last_used
      FROM switch_log sl
      JOIN environment se ON se.id = sl.environment_id
      GROUP BY se.project_id
    ) pl ON pl.project_id = p.id
    ORDER BY p.name, e.name
  `).all() as any[];

  const projects: Record<number, { id: number; name: string; last_used: string | null; environments: any[]; _envIds: Set<number> }> = {};
  for (const row of rows) {
    if (!projects[row.id]) {
      projects[row.id] = { id: row.id, name: row.name, last_used: null, environments: [], _envIds: new Set() };
    }
    projects[row.id].last_used = row.last_used ?? projects[row.id].last_used;
    if (row.env_id && !projects[row.id]._envIds.has(row.env_id)) {
      projects[row.id]._envIds.add(row.env_id);
      projects[row.id].environments.push({
        id: row.env_id,
        name: row.env_name,
        branch_name: row.branch_name,
        github_url: row.github_url ?? null,
        sh_url: row.sh_url ?? null,
        last_used_at: row.last_used_at ?? null,
        database: row.database_name,
        version: row.version_name,
        is_active: Boolean(row.is_active),
        pinned: Boolean(row.pinned),
        status: row.status ?? "active",
      });
    }
  }
  return Object.values(projects).map(({ _envIds, ...p }) => p) as Project[];
}
