import { NextResponse } from "next/server";
import { rpcCall } from "@/lib/rpc";

// Edit a workspace's DB fields. Worktree creation/consolidation stays CLI-only
// (filesystem + git); this only touches the record via the workspace.* service.
export async function PATCH(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const body = (await req.json()) as Partial<{
      name: string; path: string; is_rnd: boolean; version_id: number;
    }>;
    const fields: Record<string, unknown> = { workspace_id: Number(id) };
    if (typeof body.name === "string") fields.name = body.name.trim();
    if (typeof body.path === "string") fields.path = body.path.trim();
    if (typeof body.is_rnd === "boolean") fields.is_rnd = body.is_rnd;
    if (typeof body.version_id === "number" && body.version_id > 0) fields.version_id = body.version_id;
    await rpcCall("workspace.update", fields);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    await rpcCall("workspace.delete", { workspace_id: Number(id) });
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
