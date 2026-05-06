import type { FastifyReply, FastifyRequest } from "fastify";
import type { AppConfig } from "../config";
import type { CookieSigner } from "./cookies";
import type { ServerSession, SessionStore } from "./store";

export const SID_COOKIE = "sid";
export const CSRF_COOKIE = "csrf";

export interface SessionAttachments {
  session?: ServerSession;
}

declare module "fastify" {
  interface FastifyRequest {
    session?: ServerSession;
  }
}

export interface SessionMiddlewareDeps {
  config: AppConfig;
  store: SessionStore;
  signer: CookieSigner;
  refreshTokens(refreshToken: string): Promise<{
    idToken: string;
    accessToken: string;
    refreshToken: string;
    expiresAt: number;
  }>;
}

const REFRESH_SKEW_MS = 5 * 60 * 1000;

export function sessionMiddleware(deps: SessionMiddlewareDeps) {
  return async function loadSession(req: FastifyRequest, reply: FastifyReply): Promise<void> {
    const signed = req.cookies[SID_COOKIE];
    if (!signed) return;
    const sessionId = deps.signer.verify(signed);
    if (!sessionId) {
      reply.clearCookie(SID_COOKIE, { path: "/" });
      return;
    }
    const session = deps.store.get(sessionId);
    if (!session) {
      reply.clearCookie(SID_COOKIE, { path: "/" });
      reply.clearCookie(CSRF_COOKIE, { path: "/" });
      return;
    }
    // Refresh if token expiring soon.
    if (Date.now() > session.expiresAt - REFRESH_SKEW_MS) {
      try {
        const tokens = await deps.refreshTokens(session.refreshToken);
        session.idToken = tokens.idToken;
        session.accessToken = tokens.accessToken;
        session.refreshToken = tokens.refreshToken;
        session.expiresAt = tokens.expiresAt;
        deps.store.set(session);
      } catch {
        deps.store.delete(session.id);
        reply.clearCookie(SID_COOKIE, { path: "/" });
        reply.clearCookie(CSRF_COOKIE, { path: "/" });
        return;
      }
    }
    req.session = session;
  };
}

export function requireAuth(req: FastifyRequest, reply: FastifyReply): ServerSession {
  if (!req.session) {
    void reply.code(401).send({
      error: {
        code: "UNAUTHENTICATED",
        message: "会话已过期，请重新登录",
        request_id: req.id,
      },
    });
    throw new Error("UNAUTHENTICATED");
  }
  return req.session;
}
