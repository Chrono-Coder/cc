import { NextResponse } from "next/server";
import { rpcCall } from "@/lib/rpc";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const query = searchParams.get("q") || searchParams.get("symbol");
    if (!query) {
      return NextResponse.json({ error: "missing query" }, { status: 400 });
    }
    const params: Record<string, unknown> = {
      query,
      limit: parseInt(searchParams.get("limit") || "", 10) || 20,
    };
    const since = searchParams.get("since");
    const until = searchParams.get("until");
    if (since) params.since = since;
    if (until) params.until = until;

    const result = await rpcCall("intel.search", params);
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
