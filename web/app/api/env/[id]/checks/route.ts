import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { ghCommitStatus, ghPRForBranch } from "@/lib/gh";

export type CheckRun = {
  id: number;
  context: string;
  state: "success" | "pending" | "error" | "failure";
  description: string | null;
  target_url: string | null;
  updated_at: string;
};

export type PR = {
  number: number;
  title: string;
  html_url: string;
  state: string;
  draft: boolean;
  created_at: string;
};

export type ChecksResponse = {
  runs: CheckRun[];
  pr: PR | null;
  repo: string;
  branch: string;
};

const CACHE_TTL = 60 * 1000;
const cache = new Map<string, { data: unknown; ts: number }>();

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const cached = cache.get(id);
  if (cached && Date.now() - cached.ts < CACHE_TTL) return NextResponse.json(cached.data);

  const db = getDb();

  const env = db.prepare(`
    SELECT e.github_url, e.branch_name
    FROM environment e
    WHERE e.id = ?
  `).get(Number(id)) as { github_url: string | null; branch_name: string | null } | undefined;

  if (!env?.github_url) return NextResponse.json({ error: "No GitHub URL for this environment." }, { status: 400 });
  if (!env?.branch_name) return NextResponse.json({ error: "No branch set for this environment." }, { status: 400 });

  const repo = env.github_url.replace("https://github.com/", "").replace(/\/$/, "");
  const branch = env.branch_name;

  try {
    const runs = ghCommitStatus(repo, branch);
    const pr = ghPRForBranch(repo, branch);

    const result = { runs, pr, repo, branch } satisfies ChecksResponse;
    cache.set(id, { data: result, ts: Date.now() });
    return NextResponse.json(result);
  } catch (e) {
    if (String(e).includes("404")) {
      const result = { runs: [], pr: null, repo, branch } satisfies ChecksResponse;
      cache.set(id, { data: result, ts: Date.now() });
      return NextResponse.json(result);
    }
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
