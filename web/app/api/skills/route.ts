import { NextResponse } from "next/server";
import { rpcCall } from "@/lib/rpc";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const params: Record<string, unknown> = { top: 25 };
    const since = searchParams.get("since");
    const until = searchParams.get("until");
    const repoId = searchParams.get("repo_id");
    if (since) params.since = since;
    if (until) params.until = until;
    if (repoId) params.repository_id = Number(repoId);

    const result = await rpcCall("intel.skills", params);
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
