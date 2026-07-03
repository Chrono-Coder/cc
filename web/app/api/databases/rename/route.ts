import { NextResponse } from "next/server";
import { rpcCall } from "@/lib/rpc";

export async function POST(req: Request) {
  try {
    const { id, old_name, new_name } = await req.json();
    if (
      typeof id !== "number" ||
      !old_name || !new_name ||
      typeof old_name !== "string" || typeof new_name !== "string" ||
      !/^[\w\-. ]+$/.test(old_name) || !/^[\w\-. ]+$/.test(new_name)
    ) {
      return NextResponse.json({ error: "Invalid request" }, { status: 400 });
    }
    await rpcCall("pg.rename_db", { old_name, new_name });
    await rpcCall("database.update", { database_id: id, name: new_name });
    return NextResponse.json({ ok: true });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message.trim() : String(e);
    return NextResponse.json({ error: msg || "Rename failed" }, { status: 500 });
  }
}
