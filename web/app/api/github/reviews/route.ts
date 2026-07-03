import { NextResponse } from "next/server";
import { ghUsername, ghSearchPRs } from "@/lib/gh";

export type { GithubPR } from "@/lib/api";

const CACHE_TTL = 60 * 1000;
let cache: { data: unknown; ts: number } | null = null;

export async function GET() {
  if (cache && Date.now() - cache.ts < CACHE_TTL) {
    return NextResponse.json(cache.data);
  }

  const username = ghUsername();
  if (!username) {
    return NextResponse.json(
      { error: "gh CLI not authenticated. Run: gh auth login" },
      { status: 400 },
    );
  }

  try {
    const [needsReview, myPRs] = [
      ghSearchPRs({ reviewer: username }),
      ghSearchPRs({ author: username }),
    ];
    const result = { needs_review: needsReview, my_prs: myPRs };
    cache = { data: result, ts: Date.now() };
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
