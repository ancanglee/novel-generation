import fastifyRateLimit from "@fastify/rate-limit";
import type { FastifyInstance } from "fastify";
import { SID_COOKIE } from "../session/middleware.js";

export async function registerRateLimit(app: FastifyInstance): Promise<void> {
  await app.register(fastifyRateLimit, {
    global: false,
  });

  // Telemetry endpoint — per-session limiter.
  app.addHook("onRoute", (route) => {
    if (route.url === "/telemetry" && route.method === "POST") {
      route.preHandler = [
        ...(Array.isArray(route.preHandler)
          ? route.preHandler
          : route.preHandler
            ? [route.preHandler]
            : []),
        app.rateLimit({
          max: 100,
          timeWindow: "1 second",
          keyGenerator: (req) => req.cookies[SID_COOKIE] ?? req.ip,
          errorResponseBuilder: (_req, context) => ({
            error: {
              code: "RATE_LIMITED",
              message: `Too many telemetry events; retry after ${context.after}`,
              request_id: "unknown",
            },
          }),
        }) as never,
      ];
    }
  });
}
