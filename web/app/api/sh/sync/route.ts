import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { rpcCall } from "@/lib/rpc";

function normalizeGithubUrl(url: string): string {
  // Convert SSH format: git@github.com:org/repo → https://github.com/org/repo
  url = url.replace(/^git@github\.com:/, "https://github.com/");
  return url.replace(/\.git$/, "").replace(/\/$/, "").toLowerCase();
}

async function fetchShProjects(session: string): Promise<{ slug: string; sh_url: string; github_url: string | null }[]> {
  const res = await fetch("https://www.odoo.sh/project", {
    headers: { "Cookie": `session_id=${session}` },
  });
  const html = await res.text();

  const chunks = html.split(/(?=<div[^>]+o_project_card_container)/);
  const projects = [];

  for (const chunk of chunks) {
    const slugMatch = chunk.match(/data-name="([a-zA-Z0-9_-]+)"/);
    if (!slugMatch) continue;
    const slug = slugMatch[1];
    if (["Header", "Navbar"].includes(slug)) continue;

    const githubMatch = chunk.match(/https:\/\/github\.com\/[a-zA-Z0-9_.\-]+\/[a-zA-Z0-9_.\-]+(?:\.git)?/);
    const github_url = githubMatch ? githubMatch[0].replace(/\.git$/, "") : null;

    projects.push({ slug, sh_url: `https://www.odoo.sh/project/${slug}`, github_url });
  }

  return projects;
}

export async function POST() {
  const db = getDb();

  const row = db.prepare(`SELECT value FROM setting WHERE name = 'sh_session_id'`).get() as { value: string } | undefined;
  if (!row?.value) return NextResponse.json({ error: "No SH session. Go to /settings." }, { status: 400 });

  // Fetch all SH projects
  const shProjects = await fetchShProjects(row.value);

  // Build a map: normalized github_url → sh_url
  const shByGithub = new Map<string, string>();
  for (const p of shProjects) {
    if (p.github_url) shByGithub.set(normalizeGithubUrl(p.github_url), p.sh_url);
  }

  // Get all CC environments with github_url
  const envs = db.prepare(`
    SELECT e.id as env_id, e.name as env_name, p.name as project_name, e.github_url
    FROM environment e
    JOIN project p ON p.id = e.project_id
    WHERE e.github_url IS NOT NULL
  `).all() as { env_id: number; env_name: string; project_name: string; github_url: string }[];

  const matched: { env: string; sh_url: string }[] = [];
  const unmatched: string[] = [];

  for (const env of envs) {
    const key = normalizeGithubUrl(env.github_url);
    const sh_url = shByGithub.get(key);
    if (sh_url) {
      await rpcCall("env.update", { env_id: env.env_id, sh_url });
      matched.push({ env: env.env_name, sh_url });
    } else {
      unmatched.push(env.env_name);
    }
  }

  return NextResponse.json({
    matched: matched.length,
    unmatched: unmatched.length,
    matched_envs: matched,
    unmatched_envs: unmatched,
  });
}
