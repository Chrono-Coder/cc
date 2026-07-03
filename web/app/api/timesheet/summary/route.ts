import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";

export function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const days = Math.min(90, Math.max(1, Number(searchParams.get("days") ?? 30)));
    const cutoff = new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);

    const db = getDb();

    // Fetch all switch_log rows in range (including stop entries: environment_id IS NULL)
    // plus the first entry AFTER the range so the last in-range entry gets a proper end time
    const allRows = db.prepare(`
      SELECT
        sl.switched_at,
        sl.environment_id,
        sl.flagged,
        e.name as env_name,
        p.name as project_name
      FROM switch_log sl
      LEFT JOIN environment e ON e.id = sl.environment_id
      LEFT JOIN project p ON p.id = e.project_id
      WHERE sl.switched_at >= ?
      ORDER BY sl.switched_at ASC
    `).all(cutoff) as { switched_at: string; environment_id: number | null; flagged: number; env_name: string | null; project_name: string | null }[];

    if (!allRows.length) return NextResponse.json([]);

    const today = new Date().toISOString().slice(0, 10);

    const result: { date: string; project: string; minutes: number; flagged: boolean }[] = [];

    for (let i = 0; i < allRows.length; i++) {
      const entry = allRows[i];

      // Skip stop entries — they're only used as end-time markers for the preceding entry
      if (entry.environment_id === null) continue;
      
      if (!entry.project_name) {
        console.log("Skipping entry with missing project name:", entry);
        continue;
      }
      const date = entry.switched_at.slice(0, 10);
      const start = new Date(entry.switched_at).getTime();

      const next = allRows[i + 1] ?? null;
      let end: number;

      if (next) {
        // Next entry is a switch or a stop marker — both give the correct end time
        end = new Date(next.switched_at).getTime();
      } else if (date === today) {
        // Last entry overall and it's today — still running
        end = Date.now();
      } else {
        // Last entry of a past day with no following entry and no stop marker — skip
        end = start;
      }

      // Cap at midnight so a span doesn't bleed into the next day
      const midnight = new Date(`${date}T23:59:59.999`).getTime();
      const clampedEnd = Math.min(end, midnight);
      result.push({
        date,
        project: entry.project_name!,
        minutes: Math.round(Math.max(0, clampedEnd - start) / 60000 * 10) / 10,
        flagged: Boolean(entry.flagged),
      });
    }

    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
