import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { rpcCall } from "@/lib/rpc";

const VALID = ["active", "merged", "archived"];

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const { status } = (await req.json()) as { status?: string };
    if (!status || !VALID.includes(status)) {
      return NextResponse.json({ error: "Invalid status" }, { status: 400 });
    }
    const db = getDb();
    const row = db.prepare("SELECT id FROM environment WHERE id = ?").get(Number(id)) as
      | { id: number }
      | undefined;
    if (!row) return NextResponse.json({ error: "Not found" }, { status: 404 });

    const result = (await rpcCall("env.set_status", { env_id: row.id, status })) as { status: string };
    return NextResponse.json({ status: result.status });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
