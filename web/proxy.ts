import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import crypto from "crypto";
import fs from "fs";
import os from "os";
import path from "path";

// Local-only auth gate for the companion app.
//
// Three layers, all cheap:
//  1. Host allowlist: rejects DNS-rebinding (attacker domain resolving to
//     127.0.0.1 arrives with a foreign Host header).
//  2. Foreign-Origin rejection on mutations: kills drive-by CSRF, including
//     the text/plain "simple request" variant that never triggers a preflight.
//  3. Token auth when ~/.cc-cli/web.token exists: `cc web` generates the token
//     and opens the browser with ?token=..., which is exchanged here for an
//     httpOnly SameSite=Strict cookie. SSR self-fetches present it as a
//     Bearer header instead (lib/api.ts).

const TOKEN_PATH = path.join(os.homedir(), ".cc-cli", "web.token");
const COOKIE = "cc_web_token";
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

let cache: { mtimeMs: number; token: string | null } | null = null;

function readToken(): string | null {
  try {
    const st = fs.statSync(TOKEN_PATH);
    if (!cache || cache.mtimeMs !== st.mtimeMs) {
      const raw = fs.readFileSync(TOKEN_PATH, "utf8").trim();
      cache = { mtimeMs: st.mtimeMs, token: raw || null };
    }
    return cache.token;
  } catch {
    // No token file: token auth disabled. The server still binds 127.0.0.1
    // and layers 1-2 still apply.
    return null;
  }
}

function tokenMatches(candidate: string | null | undefined, token: string): boolean {
  if (!candidate) return false;
  const a = Buffer.from(candidate);
  const b = Buffer.from(token);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function bareHost(hostHeader: string): string {
  // "[::1]:3000" → "[::1]", "127.0.0.1:3000" → "127.0.0.1"
  if (hostHeader.startsWith("[")) return hostHeader.slice(0, hostHeader.indexOf("]") + 1);
  return hostHeader.split(":")[0];
}

function originIsLocal(origin: string): boolean {
  try {
    return LOCAL_HOSTS.has(new URL(origin).hostname);
  } catch {
    return false;
  }
}

export function proxy(req: NextRequest) {
  // CC_WEB_ALLOW_REMOTE=1 opts out of the Host allowlist for deliberate
  // trusted-LAN deployments (deploy/cc-web.service on a home server). The
  // foreign-Origin mutation guard below still applies.
  const allowRemote = process.env.CC_WEB_ALLOW_REMOTE === "1";
  const host = req.headers.get("host") ?? "";
  if (!allowRemote && !LOCAL_HOSTS.has(bareHost(host))) {
    return new NextResponse("cc web only accepts local requests", { status: 403 });
  }

  const method = req.method.toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    const origin = req.headers.get("origin");
    if (origin && !originIsLocal(origin)) {
      return new NextResponse("cross-origin requests are not allowed", { status: 403 });
    }
  }

  const token = readToken();
  if (!token) return NextResponse.next();

  const url = req.nextUrl;
  const queryToken = url.searchParams.get("token");
  if (queryToken && tokenMatches(queryToken, token)) {
    // Exchange the query token for a cookie and clean the URL.
    const clean = url.clone();
    clean.searchParams.delete("token");
    const res = NextResponse.redirect(clean);
    res.cookies.set(COOKIE, token, { httpOnly: true, sameSite: "strict", path: "/" });
    return res;
  }

  const auth = req.headers.get("authorization");
  const bearer = auth?.startsWith("Bearer ") ? auth.slice(7) : null;
  if (tokenMatches(bearer, token) || tokenMatches(req.cookies.get(COOKIE)?.value, token)) {
    return NextResponse.next();
  }

  if (url.pathname.startsWith("/api/")) {
    return NextResponse.json(
      { error: "unauthorized: open the companion via `cc web`" },
      { status: 401 },
    );
  }
  return new NextResponse(
    "Unauthorized. Start the companion with `cc web`: it opens the browser with a login token.",
    { status: 401 },
  );
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
