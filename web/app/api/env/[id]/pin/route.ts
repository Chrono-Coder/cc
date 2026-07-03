import { NextResponse } from "next/server";
import { rpcCall } from "@/lib/rpc";

export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const pinned = await rpcCall("env.toggle_pin", { env_id: Number(id) }) as boolean;
    return NextResponse.json({ pinned });
  } catch (e) {
    const msg = String(e);
    if (msg.includes("not found")) return NextResponse.json({ error: "Not found" }, { status: 404 });
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
