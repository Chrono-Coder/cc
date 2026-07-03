import net from "net";
import os from "os";
import path from "path";

const SOCKET_PATH = path.join(os.homedir(), ".cc-cli", "cc.sock");
let _requestId = 0;

export function rpcCall(
  method: string,
  params: Record<string, unknown> = {}
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const id = ++_requestId;
    const payload =
      JSON.stringify({ jsonrpc: "2.0", method, params, id }) + "\n";
    const socket = net.createConnection(SOCKET_PATH);
    let buf = "";

    socket.on("connect", () => socket.write(payload));
    socket.on("data", (chunk) => {
      buf += chunk.toString();
      if (!buf.includes("\n")) return;
      socket.destroy();
      try {
        const res = JSON.parse(buf.trim());
        if (res.error) reject(new Error(res.error.message));
        else resolve(res.result);
      } catch (e) {
        reject(e);
      }
    });
    socket.on("error", (e) =>
      reject(new Error(`CC daemon unavailable: ${e.message}`))
    );
  });
}

/**
 * Open a long-lived subscribe connection to the daemon.
 * Calls onEvent for each published event. Closes when signal is aborted.
 * Silently no-ops if the daemon is unavailable.
 */
export function rpcSubscribe(
  onEvent: (event: Record<string, unknown>) => void,
  signal: AbortSignal
): void {
  const id = ++_requestId;
  const payload =
    JSON.stringify({ jsonrpc: "2.0", method: "system.subscribe", params: {}, id }) + "\n";

  let socket: net.Socket;
  try {
    socket = net.createConnection(SOCKET_PATH);
  } catch {
    return; // Daemon unavailable
  }

  let buf = "";

  signal.addEventListener("abort", () => {
    try { socket.destroy(); } catch { /* already gone */ }
  });

  socket.on("connect", () => socket.write(payload));

  socket.on("data", (chunk) => {
    buf += chunk.toString();
    let idx: number;
    while ((idx = buf.indexOf("\n")) !== -1) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 1);
      if (!line) continue;
      try {
        const msg = JSON.parse(line) as Record<string, unknown>;
        if (msg.event && typeof msg.event === "object") {
          onEvent(msg.event as Record<string, unknown>);
        }
        // Skip ACK {"result":"subscribed"} and keep-alives {"ping":1}
      } catch { /* malformed — skip */ }
    }
  });

  socket.on("error", () => {}); // Daemon unavailable — SSE stream just stops getting events
}
