import type { FastifyReply, FastifyRequest } from "fastify";
import { request as undiciRequest } from "undici";
import type { AppConfig } from "../config.js";
import type { ServerSession } from "../session/store.js";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
]);

export async function proxyToApi(
  req: FastifyRequest,
  reply: FastifyReply,
  session: ServerSession,
  config: AppConfig,
): Promise<void> {
  const upstreamUrl = `${config.API_BASE_URL.replace(/\/$/, "")}${req.url}`;
  const method = req.method.toUpperCase();
  const body =
    method === "GET" || method === "HEAD"
      ? undefined
      : typeof req.body === "string"
        ? req.body
        : JSON.stringify(req.body ?? {});
  try {
    const upstream = await undiciRequest(upstreamUrl, {
      method: method as "GET",
      headers: {
        authorization: `Bearer ${session.idToken}`,
        "x-team-id": session.principal.teamId,
        "content-type": req.headers["content-type"] ?? "application/json",
        "x-request-id": req.id,
      },
      body,
      bodyTimeout: 30_000,
      headersTimeout: 10_000,
    });
    reply.code(upstream.statusCode);
    for (const [k, v] of Object.entries(upstream.headers)) {
      const key = k.toLowerCase();
      if (HOP_BY_HOP.has(key)) continue;
      if (Array.isArray(v)) reply.header(k, v);
      else if (v !== undefined) reply.header(k, v as string);
    }
    if (upstream.statusCode >= 500) {
      reply.header("x-upstream-error", `apiservice:${upstream.statusCode}`);
    }
    return reply.send(upstream.body);
  } catch (err: unknown) {
    const code = (err as { code?: string })?.code ?? "UNKNOWN";
    req.log.warn({ err, code }, "upstream_unreachable");
    reply.header("x-upstream-error", `bff:${code}`);
    return reply.code(502).send({
      error: {
        code: "UPSTREAM_UNREACHABLE",
        message: "上游服务暂时不可用",
        request_id: req.id,
      },
    });
  }
}
