import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";

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

// Reads the PG metadata cache the daemon maintains (database.reconcile), so this
// route is pure SQLite — no per-request psql round-trip (previously ~500ms).
export function GET() {
  try {
    const db = getDb();

    const rows = db.prepare(`
      SELECT
        d.id         AS db_id,
        d.name       AS db_name,
        d.size_bytes AS size_bytes,
        d.last_login AS last_login,
        d.is_odoo    AS is_odoo,
        d.in_pg      AS in_pg,
        e.name       AS env_name,
        p.name       AS project_name,
        CASE WHEN e.database_id = d.id THEN 1 ELSE 0 END AS is_active
      FROM "database" d
      LEFT JOIN database_environment_rel rel ON rel.database_id = d.id
      LEFT JOIN environment e ON e.id = rel.environment_id
      LEFT JOIN project p ON p.id = e.project_id
      ORDER BY d.name, p.name, e.name
    `).all() as {
      db_id: number; db_name: string;
      size_bytes: number | null; last_login: string | null;
      is_odoo: number | null; in_pg: number | null;
      env_name: string | null; project_name: string | null; is_active: number;
    }[];

    const dbMap = new Map<number, DbRecord>();
    for (const row of rows) {
      if (!dbMap.has(row.db_id)) {
        dbMap.set(row.db_id, {
          id: row.db_id,
          name: row.db_name,
          size_bytes: row.size_bytes ?? null,
          last_login: row.last_login ?? null,
          is_odoo: Boolean(row.is_odoo),
          in_pg: Boolean(row.in_pg),
          envs: [],
        });
      }
      if (row.env_name && row.project_name) {
        dbMap.get(row.db_id)!.envs.push({ name: row.env_name, project: row.project_name, is_active: row.is_active === 1 });
      }
    }

    return NextResponse.json(Array.from(dbMap.values()));
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
