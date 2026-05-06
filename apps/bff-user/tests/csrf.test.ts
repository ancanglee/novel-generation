import fastifyCookie from "@fastify/cookie";
import Fastify, { type FastifyInstance } from "fastify";
import { beforeEach, describe, expect, it } from "vitest";
import { csrfGuard } from "../src/security/csrf";

async function makeApp(): Promise<FastifyInstance> {
  const app = Fastify();
  await app.register(fastifyCookie);
  app.addHook("preHandler", async (req, reply) => {
    if (req.cookies.sid === "valid") {
      req.session = {
        id: "sid",
        idToken: "",
        accessToken: "",
        refreshToken: "",
        expiresAt: Date.now() + 10_000,
        csrfToken: "token-abc",
        createdAt: Date.now(),
        lastSeenAt: Date.now(),
        principal: { userId: "u", teamId: "t", email: "", globalRole: "", teamRole: "" },
      };
    }
  });
  app.addHook("preHandler", csrfGuard);
  app.get("/read", async () => ({ ok: true }));
  app.post("/write", async () => ({ ok: true }));
  app.post("/auth/callback", async () => ({ ok: true })); // exempt
  return app;
}

describe("csrfGuard", () => {
  let app: FastifyInstance;
  beforeEach(async () => {
    app = await makeApp();
  });

  it("allows GET without token", async () => {
    const resp = await app.inject({ method: "GET", url: "/read" });
    expect(resp.statusCode).toBe(200);
  });

  it("allows exempt path POST without token", async () => {
    const resp = await app.inject({ method: "POST", url: "/auth/callback" });
    expect(resp.statusCode).toBe(200);
  });

  it("blocks POST without token", async () => {
    const resp = await app.inject({
      method: "POST",
      url: "/write",
      cookies: { sid: "valid" },
    });
    expect(resp.statusCode).toBe(403);
  });

  it("blocks POST with mismatched cookie/header tokens", async () => {
    const resp = await app.inject({
      method: "POST",
      url: "/write",
      cookies: { sid: "valid", csrf: "token-abc" },
      headers: { "x-csrf-token": "WRONG" },
    });
    expect(resp.statusCode).toBe(403);
  });

  it("passes POST with matching triple token", async () => {
    const resp = await app.inject({
      method: "POST",
      url: "/write",
      cookies: { sid: "valid", csrf: "token-abc" },
      headers: { "x-csrf-token": "token-abc" },
    });
    expect(resp.statusCode).toBe(200);
  });
});
