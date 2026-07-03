import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const days = Math.min(90, Math.max(1, Number(searchParams.get("days") ?? 30)));
    const cutoff = new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);

    const db = getDb();
    const rows = db.prepare(`
      SELECT
        sl.id, sl.switched_at, sl.flagged,
        e.name as env_name,
        p.name as project_name
      FROM switch_log sl
      JOIN environment e ON e.id = sl.environment_id
      JOIN project p ON p.id = e.project_id
      WHERE sl.switched_at >= ?
      ORDER BY sl.switched_at ASC
    `).all(cutoff);

    return NextResponse.json(rows);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
