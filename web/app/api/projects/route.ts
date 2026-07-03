import { NextResponse } from "next/server";
import { getProjects } from "@/lib/serverData";

export function GET() {
  try {
    return NextResponse.json(getProjects());
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
