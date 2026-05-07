import type { Readable } from "node:stream";
import type { FastifyReply, FastifyRequest } from "fastify";
import { request as undiciRequest } from "undici";
import type { AppConfig } from "../config";
import type { ServerSession } from "../session/store";

export async function proxySse(
  req: FastifyRequest,
  reply: FastifyReply,
  session: ServerSession,
  config: AppConfig,
): Promise<void> {
  const upstreamUrl = `${config.API_BASE_URL.replace(/\/$/, "")}${req.url}`;
  reply.raw.setHeader("Content-Type", "text/event-stream");
  reply.raw.setHeader("Cache-Control", "no-cache, no-transform");
  reply.raw.setHeader("Connection", "keep-alive");
  reply.raw.setHeader("X-Accel-Buffering", "no");
  reply.raw.flushHeaders();

  const lastEventId = req.headers["last-event-id"];
  const upstreamHeaders: Record<string, string> = {
    authorization: `Bearer ${session.idToken}`,
    "x-team-id": session.principal.teamId,
    accept: "text/event-stream",
    "x-request-id": req.id,
  };
  if (typeof lastEventId === "string") upstreamHeaders["last-event-id"] = lastEventId;

  let upstreamBody: Readable | null = null;
  const onClientClose = (): void => {
    try {
      upstreamBody?.destroy();
    } catch {
      /* noop */
    }
  };
  req.raw.on("close", onClientClose);

  try {
    const upstream = await undiciRequest(upstreamUrl, {
      method: "GET",
      headers: upstreamHeaders,
      bodyTimeout: 0,
      headersTimeout: 10_000,
    });
    if (upstream.statusCode >= 400) {
      reply.raw.write(
        `event: error\ndata: ${JSON.stringify({
          code: `UPSTREAM_${upstream.statusCode}`,
          status: upstream.statusCode,
        })}\n\n`,
      );
      reply.raw.end();
      return;
    }
    upstreamBody = upstream.body as unknown as Readable;
    upstreamBody.on("data", (chunk: Buffer) => {
      reply.raw.write(chunk);
    });
    upstreamBody.on("end", () => {
      reply.raw.end();
    });
    upstreamBody.on("error", (err: unknown) => {
      req.log.warn({ err }, "sse_upstream_error");
      try {
        reply.raw.write(`event: error\ndata: ${JSON.stringify({ code: "SSE_PIPE_ERROR" })}\n\n`);
      } finally {
        reply.raw.end();
      }
    });
  } catch (err) {
    req.log.warn({ err }, "sse_connect_failed");
    reply.raw.write(`event: error\ndata: ${JSON.stringify({ code: "SSE_CONNECT_FAILED" })}\n\n`);
    reply.raw.end();
  }
}
