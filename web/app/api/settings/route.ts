import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { rpcCall } from "@/lib/rpc";

// Sensitive settings never leave the server: return "set" / null instead of
// the value. Explicit keys plus a suffix pattern so new credential-shaped
// keys (sync.api_key, github_pat, ...) are masked without a code change.
const SENSITIVE_KEYS = new Set(["sh_session_id", "pg.connection"]);
const SENSITIVE_RE = /(key|token|secret|passw|pat)$/i;

function isSensitive(name: string): boolean {
  return SENSITIVE_KEYS.has(name) || SENSITIVE_RE.test(name);
}

// Web-managed keys that live outside the config schema (integrations etc.)
const WEB_EXTRA_WRITABLE = new Set(["sh_session_id"]);

type SchemaEntry = {
  key?: string;
  type?: string;
  options?: Record<string, string>;
};

export function GET() {
  const db = getDb();
  const rows = db.prepare(`SELECT name, value FROM setting`).all() as { name: string; value: string }[];
  const result: Record<string, string | null> = {};
  for (const r of rows) {
    result[r.name] = isSensitive(r.name) ? (r.value ? "set" : null) : (r.value ?? null);
  }
  return NextResponse.json(result);
}

export async function POST(request: Request) {
  const body = await request.json();

  // Writable = config-schema keys (the source of truth) + web-managed extras.
  let byKey: Map<string, SchemaEntry>;
  try {
    const schema = (await rpcCall("setting.schema")) as SchemaEntry[];
    byKey = new Map(schema.filter((s) => s.key).map((s) => [s.key as string, s]));
  } catch {
    byKey = new Map();
  }

  for (const [key, value] of Object.entries(body)) {
    const entry = byKey.get(key);
    if (!entry && !WEB_EXTRA_WRITABLE.has(key)) continue;
    if (typeof value !== "string") continue;
    const trimmed = value.trim();
    // Never let the GET mask sentinel round-trip over a real secret.
    if (isSensitive(key) && trimmed === "set") continue;
    // Select-type settings only accept declared option values. This matters
    // for `ide`: its value feeds a subprocess launch on the next
    // `cc project open`, so a free-form write would persist an arbitrary
    // command for later execution.
    if (entry?.type === "select" && entry.options) {
      const allowed = new Set(Object.values(entry.options));
      if (!allowed.has(trimmed)) continue;
    }
    await rpcCall("setting.upsert", { key, value: trimmed });
  }

  return NextResponse.json({ ok: true });
}
