import type { FastifyReply, FastifyRequest } from "fastify";
import { CSRF_COOKIE } from "../session/middleware";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const CSRF_EXEMPT_PATHS = new Set(["/auth/callback", "/auth/login", "/healthz"]);

export async function csrfGuard(req: FastifyRequest, reply: FastifyReply): Promise<void> {
  if (SAFE_METHODS.has(req.method.toUpperCase())) return;
  if (CSRF_EXEMPT_PATHS.has(req.url.split("?")[0] ?? req.url)) return;
  const headerToken = req.headers["x-csrf-token"];
  const cookieToken = req.cookies[CSRF_COOKIE];
  const sessionToken = req.session?.csrfToken;
  if (
    typeof headerToken !== "string" ||
    typeof cookieToken !== "string" ||
    !sessionToken ||
    headerToken !== cookieToken ||
    headerToken !== sessionToken
  ) {
    void reply.code(403).send({
      error: {
        code: "CSRF_VALIDATION_FAILED",
        message: "请求被拒绝，请刷新页面重试",
        request_id: req.id,
      },
    });
    throw new Error("CSRF_VALIDATION_FAILED");
  }
}
