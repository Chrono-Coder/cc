import { rpcSubscribe } from "@/lib/rpc";

export async function GET(request: Request) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      const enqueue = (data: string) => {
        try {
          controller.enqueue(encoder.encode(data));
        } catch {
          /* controller closed */
        }
      };

      // Heartbeat keeps the SSE connection alive through proxies/load balancers
      const heartbeatId = setInterval(() => enqueue(": heartbeat\n\n"), 30000);

      // Subscribe to daemon events — falls back gracefully if daemon is unavailable
      rpcSubscribe(
        (event) => {
          enqueue(`data: ${JSON.stringify(event)}\n\n`);
        },
        request.signal
      );

      request.signal.addEventListener("abort", () => {
        clearInterval(heartbeatId);
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
