import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import fs from "fs";
import path from "path";
import os from "os";
import { spawnSync } from "child_process";

function countPyLines(filePath: string): number {
  try {
    const content = fs.readFileSync(filePath, "utf8");
    return content.split("\n").filter((line) => {
      const t = line.trim();
      return t.length > 0 && !t.startsWith("#");
    }).length;
  } catch {
    return 0;
  }
}

function clocDir(dirPath: string): number {
  let total = 0;
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true });
    for (const entry of entries) {
      const full = path.join(dirPath, entry.name);
      if (entry.isDirectory()) {
        total += clocDir(full);
      } else if (entry.name.endsWith(".py")) {
        total += countPyLines(full);
      }
    }
  } catch {
    // unreadable dir
  }
  return total;
}

function isModuleDir(dirPath: string): boolean {
  return fs.existsSync(path.join(dirPath, "__manifest__.py"));
}

function clocPath(scanPath: string): { name: string; loc: number }[] {
  const results: { name: string; loc: number }[] = [];
  try {
    const entries = fs.readdirSync(scanPath, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const full = path.join(scanPath, entry.name);
      if (isModuleDir(full)) {
        results.push({ name: entry.name, loc: clocDir(full) });
      }
    }
  } catch {
    // unreadable
  }
  return results;
}

export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  let tmpDir: string | null = null;
  try {
    const { id } = await params;
    const db = getDb();

    const env = db.prepare(`
      SELECT project_path, branch_name FROM environment WHERE id = ?
    `).get(Number(id)) as { project_path: string; branch_name: string | null } | undefined;

    if (!env?.project_path) return NextResponse.json({ error: "Env not found" }, { status: 404 });

    const { project_path, branch_name } = env;

    if (!fs.existsSync(project_path)) {
      return NextResponse.json({ error: `Path not found: ${project_path}` }, { status: 404 });
    }

    let scanPath = project_path;

    // If there's a branch, use git archive to read that branch without touching
    // the checkout. Leading "-" is rejected (invalid as a ref anyway) so a
    // hostile value can't be parsed as a git flag; argv arrays mean no shell,
    // so ref names with metacharacters can't inject commands.
    if (branch_name && !branch_name.startsWith("-")) {
      try {
        tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "cc-cloc-"));
        const archive = spawnSync("git", ["-C", project_path, "archive", branch_name], {
          timeout: 30000,
          maxBuffer: 256 * 1024 * 1024,
        });
        if (archive.status !== 0) throw new Error("git archive failed");
        const untar = spawnSync("tar", ["-x", "-C", tmpDir], {
          input: archive.stdout,
          timeout: 30000,
        });
        if (untar.status !== 0) throw new Error("tar extract failed");
        scanPath = tmpDir;
      } catch {
        // Branch not found locally or git archive failed — fall back to reading from disk
        if (tmpDir) {
          fs.rmSync(tmpDir, { recursive: true, force: true });
          tmpDir = null;
        }
      }
    }

    const results = clocPath(scanPath);
    results.sort((a, b) => b.loc - a.loc);
    const total = results.reduce((s, r) => s + r.loc, 0);

    return NextResponse.json({ modules: results, total });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  } finally {
    if (tmpDir) {
      try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch { /* ignore */ }
    }
  }
}
