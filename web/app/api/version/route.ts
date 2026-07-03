import { NextResponse } from "next/server";
import { rpcCall } from "@/lib/rpc";

/** The running daemon's cc version — cheap single-RPC read for the nav. */
export async function GET() {
  try {
    const health = (await rpcCall("system.health")) as { version?: string };
    return NextResponse.json({ version: health.version ?? null });
  } catch {
    return NextResponse.json({ version: null });
  }
}
