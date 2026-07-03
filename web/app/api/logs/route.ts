import { NextRequest } from "next/server";
import fs from "fs";
import path from "path";

const LOGS_DIR = path.join(process.env.HOME || "/tmp", ".cc-cli", "logs");

const LOG_FILES: Record<string, string> = {
  all: path.join(LOGS_DIR, "cc.log"),
  rpc: path.join(LOGS_DIR, "rpc.log"),
};

type LogEntry = {
  timestamp: string;
  level: string;
  source: string;
  message: string;
};

function parseCCLine(line: string): LogEntry | null {
  // Format: 2026-05-03 19:07:18,546 - CC - DEBUG - some message
  const match = line.match(
    /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (\w+) - (\w+) - (.+)$/
  );
  if (!match) return null;
  return {
    timestamp: match[1],
    source: match[2],
    level: match[3].toLowerCase(),
    message: match[4],
  };
}

function parseRPCLine(line: string): LogEntry | null {
  // Format: 2026-05-03 19:07:18,546  OK  env.switch(...) → ... 12.3ms
  const match = line.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s{2}(.+)$/);
  if (!match) return null;

  const msg = match[2];
  const level = msg.startsWith("OK") ? "info" : msg.startsWith("ERR") ? "error" : "debug";
  return {
    timestamp: match[1],
    source: "RPC",
    level,
    message: msg,
  };
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const source = params.get("source") || "all";
  const level = params.get("level") || null;
  const lines = Math.min(parseInt(params.get("lines") || "200"), 1000);

  const logFile = LOG_FILES[source];
  if (!logFile) {
    return Response.json({ error: "Invalid source" }, { status: 400 });
  }

  if (!fs.existsSync(logFile)) {
    return Response.json([]);
  }

  const content = fs.readFileSync(logFile, "utf-8");
  const rawLines = content.split("\n").filter(Boolean);

  const parser = source === "rpc" ? parseRPCLine : parseCCLine;
  let entries: LogEntry[] = rawLines.map(parser).filter(Boolean) as LogEntry[];

  if (level) {
    entries = entries.filter((e) => e.level === level.toLowerCase());
  }

  // Return most recent N lines
  return Response.json(entries.slice(-lines));
}
