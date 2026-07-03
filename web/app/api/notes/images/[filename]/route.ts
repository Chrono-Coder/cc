import { NextResponse } from "next/server";
import { readFile, unlink } from "fs/promises";
import path from "path";
import os from "os";

const IMAGES_DIR = path.join(os.homedir(), ".cc-cli", "notes", "images");
const SAFE = /^[a-f0-9-]+\.(png|jpg|jpeg|gif|webp)$/;

export async function GET(_req: Request, { params }: { params: Promise<{ filename: string }> }) {
  const { filename } = await params;
  if (!SAFE.test(filename)) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  try {
    const buf = await readFile(path.join(IMAGES_DIR, filename));
    const ext = filename.split(".").pop()!;
    const mime = ext === "jpg" ? "image/jpeg" : `image/${ext}`;
    return new Response(buf, { headers: { "Content-Type": mime } });
  } catch {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
}

export async function DELETE(_req: Request, { params }: { params: Promise<{ filename: string }> }) {
  const { filename } = await params;
  if (!SAFE.test(filename)) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  try {
    await unlink(path.join(IMAGES_DIR, filename));
  } catch {
    // already gone — fine
  }
  return NextResponse.json({ ok: true });
}
