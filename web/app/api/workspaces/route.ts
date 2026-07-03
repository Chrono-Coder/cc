import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export function GET() {
  try {
    const db = getDb();
    const rows = db.prepare(`
      SELECT
        w.id,
        w.name,
        w.path        AS workspace_path,
        w.is_rnd,
        v.id          AS version_id,
        v.name        AS version_name,
        v.path        AS version_path,
        v.port,
        v.branch,
        v.pyenv_virtualenv AS venv,
        v.last_fetched_at,
        (SELECT COUNT(*) FROM project p WHERE p.workspace_id = w.id) AS project_count
      FROM workspace w
      LEFT JOIN version v ON v.id = w.version_id
      ORDER BY w.name ASC
    `).all();
    return NextResponse.json(rows);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
