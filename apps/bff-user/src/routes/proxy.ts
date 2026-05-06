import type { FastifyInstance } from "fastify";
import type { AppConfig } from "../config";
import { proxySse } from "../proxy/sse";
import { proxyToApi } from "../proxy/standard";
import { requireAuth } from "../session/middleware";

const SSE_PATTERN =
  /^\/api\/v1\/generations\/[^/]+\/chapters\/[^/]+\/stream(\?.*)?$/;

export async function proxyRoutes(
  app: FastifyInstance,
  opts: { config: AppConfig },
): Promise<void> {
  app.all("/api/*", async (req, reply) => {
    const session = requireAuth(req, reply);
    if (reply.sent) return;
    if (req.method === "GET" && SSE_PATTERN.test(req.url)) {
      await proxySse(req, reply, session, opts.config);
      return;
    }
    await proxyToApi(req, reply, session, opts.config);
  });
}
