import { NextResponse } from "next/server";
import { writeFile, mkdir } from "fs/promises";
import path from "path";
import os from "os";
import { randomUUID } from "crypto";

const IMAGES_DIR = path.join(os.homedir(), ".cc-cli", "notes", "images");

export async function POST(req: Request) {
  const form = await req.formData();
  const file = form.get("file") as File | null;
  const ALLOWED_TYPES: Record<string, string> = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
  };
  if (!file || !ALLOWED_TYPES[file.type]) {
    return NextResponse.json({ error: "Unsupported image type" }, { status: 400 });
  }
  const ext = ALLOWED_TYPES[file.type];
  const filename = `${randomUUID()}.${ext}`;
  await mkdir(IMAGES_DIR, { recursive: true });
  await writeFile(path.join(IMAGES_DIR, filename), Buffer.from(await file.arrayBuffer()));
  return NextResponse.json({ url: `/api/notes/images/${filename}` });
}
