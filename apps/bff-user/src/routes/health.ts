import type { FastifyInstance } from "fastify";
import type { SessionStore } from "../session/store.js";

export async function healthRoutes(
  app: FastifyInstance,
  opts: { store: SessionStore },
): Promise<void> {
  app.get("/healthz", async () => ({ status: "ok", sessions: opts.store.size() }));
  app.get("/readyz", async () => ({ status: "ready" }));
}
