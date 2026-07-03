import { NextResponse } from "next/server";
import { rpcCall } from "@/lib/rpc";

export async function GET() {
  try {
    const result = await rpcCall("intel.list_repos");
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
