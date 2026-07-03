import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export function GET() {
  try {
    const db = getDb();
    const rows = db.prepare(`
      SELECT id, name, path, port, branch, last_fetched_at
      FROM version ORDER BY name DESC
    `).all();
    return NextResponse.json(rows);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
