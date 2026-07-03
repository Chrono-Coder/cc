import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { rpcCall } from "@/lib/rpc";

export function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const days = Math.min(90, Math.max(1, Number(searchParams.get("days") ?? 30)));
    const cutoff = new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);

    const db = getDb();
    // LEFT JOIN so stop entries (environment_id IS NULL) are included.
    const rows = db.prepare(`
      SELECT
        sl.id, sl.switched_at, sl.flagged,
        sl.environment_id, sl.ended_at, sl.note, sl.source, sl.edited,
        e.name as env_name,
        p.name as project_name
      FROM switch_log sl
      LEFT JOIN environment e ON e.id = sl.environment_id
      LEFT JOIN project p ON p.id = e.project_id
      WHERE sl.switched_at >= ?
      ORDER BY sl.switched_at ASC
    `).all(cutoff);

    return NextResponse.json(rows);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

// Create a manual entry (parity with `cc time start`). Requires env_id + started_at.
export async function PUT(request: Request) {
  try {
    const { env_id, started_at, ended_at, note } = await request.json();
    if (!env_id || !started_at) return NextResponse.json({ error: "Missing fields" }, { status: 400 });
    const res = await rpcCall("timesheet.create_entry", {
      env_id, started_at, ended_at: ended_at ?? null, note: note ?? "",
    });
    return NextResponse.json(res);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

export async function POST() {
  try {
    await rpcCall("timesheet.punch_out");
    return NextResponse.json({ ok: true });
  } catch (e) {
    const msg = String(e);
    if (msg.includes("Already punched out")) return NextResponse.json({ error: "Already stopped." }, { status: 400 });
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

// Edit start (switched_at), end (ended_at), and/or note. Editing an auto entry is
// marked authoritative server-side (timesheet.update_entry sets `edited`).
export async function PATCH(request: Request) {
  try {
    const { id, switched_at, ended_at, note } = await request.json();
    if (!id) return NextResponse.json({ error: "Missing id" }, { status: 400 });
    const params: Record<string, unknown> = { entry_id: id };
    if (switched_at !== undefined) params.switched_at = switched_at;
    if (ended_at !== undefined) params.ended_at = ended_at;
    if (note !== undefined) params.note = note;
    await rpcCall("timesheet.update_entry", params);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

export async function DELETE(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get("id");
    if (!id) return NextResponse.json({ error: "Missing id" }, { status: 400 });
    await rpcCall("timesheet.delete_entry", { entry_id: Number(id) });
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
