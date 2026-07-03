import { NextResponse } from "next/server";
import { rpcCall } from "@/lib/rpc";

// The settings registry (cc.config.schema) — the single source of truth the
// CLI and the companion both render from.
export async function GET() {
  try {
    const schema = await rpcCall("setting.schema");
    return NextResponse.json(schema);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
