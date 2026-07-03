import { NextResponse } from "next/server";
import { ghIsAvailable, ghUsername } from "@/lib/gh";

export async function GET() {
  if (!ghIsAvailable()) {
    return NextResponse.json({ authenticated: false, username: null, source: "gh CLI (not installed)" });
  }
  const username = ghUsername();
  return NextResponse.json({
    authenticated: !!username,
    username,
    source: "gh CLI",
  });
}
