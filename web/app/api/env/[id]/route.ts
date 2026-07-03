import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { rpcCall } from "@/lib/rpc";

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const db = getDb();

    const env = db.prepare(`
      SELECT
        e.id, e.name, e.project_path, e.github_url, e.branch_name, e.last_used_at, e.sh_url, e.notes, e.ticket_ids, e.pinned, e.status,
        p.id as project_id, p.name as project_name, p.is_virtual as project_is_virtual,
        v.name as version_name, v.port as version_port, v.path as version_path,
        d.name as database_name,
        CASE WHEN a.environment_id IS NOT NULL THEN 1 ELSE 0 END as is_active
      FROM environment e
      JOIN project p ON p.id = e.project_id
      LEFT JOIN version v ON v.id = e.version_id
      LEFT JOIN "database" d ON d.id = e.database_id
      LEFT JOIN app_state a ON a.environment_id = e.id
      WHERE e.id = ?
    `).get(Number(id)) as any;

    if (!env) return NextResponse.json({ error: "Not found" }, { status: 404 });

    const modules = db.prepare(`
      SELECT id, name FROM module WHERE environment_id = ? ORDER BY name
    `).all(env.id) as { id: number; name: string }[];

    // Best-effort: a flaky daemon/PG must not 404 the whole env page.
    let last_login_at: string | null = null;
    if (env.database_name) {
      try {
        last_login_at = (await rpcCall("pg.get_last_login", { db_name: env.database_name })) as string | null;
      } catch {
        last_login_at = null;
      }
    }

    return NextResponse.json({
      id: env.id,
      name: env.name,
      project_path: env.project_path,
      github_url: env.github_url ?? null,
      branch_name: env.branch_name ?? null,
      last_used_at: env.last_used_at ?? null,
      last_login_at,
      is_active: Boolean(env.is_active),
      pinned: Boolean(env.pinned),
      status: env.status ?? "active",
      sh_url: env.sh_url ?? null,
      notes: env.notes ?? null,
      ticket_ids: env.ticket_ids ? (env.ticket_ids as string).split(",").map((t: string) => t.trim()).filter(Boolean) : [],
      is_virtual: Boolean(env.project_is_virtual),
      project: { id: env.project_id, name: env.project_name },
      version: env.version_name ? { name: env.version_name, port: env.version_port ?? null, path: env.version_path ?? null } : null,
      database: env.database_name ?? null,
      modules,
    });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

export async function PATCH(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const body = await req.json() as { notes?: string | null; ticket_ids?: string[] };

    const fieldsObj: Record<string, unknown> = {};
    if ("notes" in body) fieldsObj.notes = body.notes ?? null;
    if ("ticket_ids" in body) fieldsObj.ticket_ids = body.ticket_ids?.join(",") ?? null;

    if (!Object.keys(fieldsObj).length) return NextResponse.json({ ok: true });

    await rpcCall("env.update", { env_id: Number(id), ...fieldsObj });
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
