import { execFileSync } from "child_process";
import type { GithubPR } from "./api";
import type { CheckRun, PR } from "@/app/api/env/[id]/checks/route";

// ---------------------------------------------------------------------------
// Core runner
// ---------------------------------------------------------------------------

function ghExec(args: string[], timeoutMs = 15_000): string {
  // argv array, no shell: repo/ref/branch values from the DB can't inject.
  return execFileSync("gh", args, {
    timeout: timeoutMs,
    encoding: "utf-8",
    stdio: ["pipe", "pipe", "pipe"],
  }).trim();
}

function ghJson<T = unknown>(args: string[], timeoutMs?: number): T {
  const out = ghExec(args, timeoutMs);
  return JSON.parse(out);
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export function ghIsAvailable(): boolean {
  try {
    execFileSync("gh", ["auth", "status"], { timeout: 5000, stdio: "pipe" });
    return true;
  } catch {
    return false;
  }
}

export function ghUsername(): string | null {
  try {
    return ghExec(["api", "user", "--jq", ".login"], 10_000) || null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// PR search — returns GithubPR[] matching the existing contract
// ---------------------------------------------------------------------------

type GhSearchPR = {
  number: number;
  title: string;
  url: string;
  isDraft: boolean;
  createdAt: string;
  updatedAt: string;
  author: { login: string };
  repository: { nameWithOwner: string };
};

const SEARCH_FIELDS = "number,title,url,isDraft,createdAt,updatedAt,author,repository";

export function ghSearchPRs(opts: { author?: string; reviewer?: string; limit?: number }): GithubPR[] {
  const args = ["search", "prs", "--state", "open", "--json", SEARCH_FIELDS, "--limit", String(opts.limit ?? 30)];
  if (opts.author) args.push("--author", opts.author);
  if (opts.reviewer) args.push("--review-requested", opts.reviewer);

  const raw = ghJson<GhSearchPR[]>(args, 20_000);
  return raw.map(pr => ({
    id: pr.number,
    number: pr.number,
    title: pr.title,
    html_url: pr.url,
    repo: pr.repository.nameWithOwner,
    author: pr.author.login,
    author_avatar: `https://github.com/${pr.author.login}.png`,
    created_at: pr.createdAt,
    updated_at: pr.updatedAt,
    draft: pr.isDraft,
  }));
}

// ---------------------------------------------------------------------------
// Commit status — returns statuses mapped to CheckRun[]
// ---------------------------------------------------------------------------

type GhStatus = {
  id: number;
  context: string;
  state: string;
  description: string | null;
  target_url: string | null;
  updated_at: string;
};

export function ghCommitStatus(repo: string, ref: string): CheckRun[] {
  try {
    const data = ghJson<{ statuses?: GhStatus[] }>(
      ["api", `repos/${repo}/commits/${encodeURIComponent(ref)}/status`],
    );
    return (data.statuses ?? []).map(s => ({
      id: s.id,
      context: s.context,
      state: s.state as CheckRun["state"],
      description: s.description ?? null,
      target_url: s.target_url ?? null,
      updated_at: s.updated_at,
    }));
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------
// PR list for a repo — returns PR | null for the first match
// ---------------------------------------------------------------------------

type GhPRListItem = {
  number: number;
  title: string;
  url: string;
  isDraft: boolean;
  state: string;
  createdAt: string;
  author: { login: string };
};

export function ghPRForBranch(repo: string, branch: string): PR | null {
  try {
    const items = ghJson<GhPRListItem[]>(
      ["pr", "list", "-R", repo, "--head", branch, "--state", "open", "--json", "number,title,url,isDraft,state,createdAt", "--limit", "1"],
    );
    if (!items.length) return null;
    const p = items[0];
    return {
      number: p.number,
      title: p.title,
      html_url: p.url,
      state: p.state.toLowerCase(),
      draft: p.isDraft,
      created_at: p.createdAt,
    };
  } catch {
    return null;
  }
}
