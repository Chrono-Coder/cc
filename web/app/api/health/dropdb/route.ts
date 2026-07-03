import { NextResponse } from "next/server";
import { rpcCall } from "@/lib/rpc";

export async function POST(req: Request) {
  try {
    const { name } = await req.json();
    if (!name || typeof name !== "string" || !/^[\w\-. ]+$/.test(name)) {
      return NextResponse.json({ error: "Invalid database name" }, { status: 400 });
    }
    await rpcCall("pg.drop_db", { name });
    return NextResponse.json({ ok: true });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message.trim() : String(e);
    if (msg.toLowerCase().includes("does not exist")) {
      return NextResponse.json({ ok: true });
    }
    return NextResponse.json({ error: msg || "Drop failed" }, { status: 500 });
  }
}
