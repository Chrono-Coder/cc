import { NextResponse } from "next/server";
import { rpcCall } from "@/lib/rpc";

export async function POST() {
  try {
    const cleared = await rpcCall("timesheet.clear_flags");
    return NextResponse.json({ ok: true, cleared });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
