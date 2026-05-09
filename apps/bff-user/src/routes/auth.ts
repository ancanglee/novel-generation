import type { FastifyInstance } from "fastify";
import { nanoid } from "nanoid";
import type { BaseClient, generators } from "openid-client";
import type { AppConfig } from "../config.js";
import type { CookieSigner } from "../session/cookies.js";
import { CSRF_COOKIE, SID_COOKIE } from "../session/middleware.js";
import type { SessionStore } from "../session/store.js";

export interface AuthRoutesDeps {
  config: AppConfig;
  signer: CookieSigner;
  store: SessionStore;
  oidcClient: BaseClient;
  generators: typeof generators;
}

export async function authRoutes(app: FastifyInstance, deps: AuthRoutesDeps): Promise<void> {
  const { config, signer, store, oidcClient, generators: gen } = deps;

  app.get("/auth/login", async (req, reply) => {
    const state = nanoid();
    const nonce = nanoid();
    const codeVerifier = gen.codeVerifier();
    const codeChallenge = gen.codeChallenge(codeVerifier);

    reply.setCookie("auth_state", `${state}|${codeVerifier}|${nonce}`, {
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      path: "/auth",
      maxAge: 5 * 60,
    });

    const url = oidcClient.authorizationUrl({
      scope: "openid email profile",
      state,
      nonce,
      code_challenge: codeChallenge,
      code_challenge_method: "S256",
    });
    return reply.redirect(url);
  });

  app.get("/auth/callback", async (req, reply) => {
    const raw = req.cookies.auth_state;
    if (!raw)
      return reply
        .code(400)
        .send({ error: { code: "NO_AUTH_STATE", message: "登录状态缺失", request_id: req.id } });
    const [state, codeVerifier, nonce] = raw.split("|");
    reply.clearCookie("auth_state", { path: "/auth" });

    try {
      const params = oidcClient.callbackParams(req.raw);
      const tokenSet = await oidcClient.callback(config.redirectUri, params, {
        state,
        nonce,
        code_verifier: codeVerifier,
      });
      if (!tokenSet.id_token || !tokenSet.access_token || !tokenSet.refresh_token) {
        throw new Error("TOKEN_SET_INCOMPLETE");
      }
      const claims = tokenSet.claims();
      const sessionId = nanoid(32);
      const csrfToken = nanoid(32);
      const expiresAt =
        typeof tokenSet.expires_at === "number"
          ? tokenSet.expires_at * 1000
          : Date.now() + 3600 * 1000;

      store.set({
        id: sessionId,
        idToken: tokenSet.id_token,
        accessToken: tokenSet.access_token,
        refreshToken: tokenSet.refresh_token,
        expiresAt,
        csrfToken,
        createdAt: Date.now(),
        lastSeenAt: Date.now(),
        principal: {
          userId: String(claims.sub),
          teamId: String(claims["custom:team_id"] ?? ""),
          email: String(claims.email ?? ""),
          globalRole: String(claims["custom:global_role"] ?? "regular_user"),
          teamRole: String(claims["custom:team_role"] ?? "member"),
        },
      });

      const cookieOpts = {
        httpOnly: true,
        secure: true,
        sameSite: "lax" as const,
        path: "/",
        maxAge: Math.floor(config.SESSION_TTL_HOURS * 3600),
      };
      reply.setCookie(SID_COOKIE, signer.sign(sessionId), cookieOpts);
      reply.setCookie(CSRF_COOKIE, csrfToken, {
        ...cookieOpts,
        httpOnly: false,
        sameSite: "strict",
      });
      return reply.redirect("/");
    } catch (err) {
      req.log.warn({ err }, "oidc_callback_failed");
      return reply.code(401).send({
        error: { code: "LOGIN_FAILED", message: "登录失败，请重试", request_id: req.id },
      });
    }
  });

  app.get("/auth/me", async (req, reply) => {
    if (!req.session) {
      return reply.code(401).send({
        error: { code: "UNAUTHENTICATED", message: "未登录", request_id: req.id },
      });
    }
    return {
      principal: req.session.principal,
      csrf: req.session.csrfToken,
    };
  });

  app.post("/auth/logout", async (req, reply) => {
    if (req.session) store.delete(req.session.id);
    reply.clearCookie(SID_COOKIE, { path: "/" });
    reply.clearCookie(CSRF_COOKIE, { path: "/" });
    return { ok: true };
  });
}

export async function refreshTokensFactory(client: BaseClient): Promise<
  (refreshToken: string) => Promise<{
    idToken: string;
    accessToken: string;
    refreshToken: string;
    expiresAt: number;
  }>
> {
  return async (refreshToken: string) => {
    const tokenSet = await client.refresh(refreshToken);
    if (!tokenSet.id_token || !tokenSet.access_token) {
      throw new Error("REFRESH_FAILED");
    }
    return {
      idToken: tokenSet.id_token,
      accessToken: tokenSet.access_token,
      refreshToken: tokenSet.refresh_token ?? refreshToken,
      expiresAt:
        typeof tokenSet.expires_at === "number"
          ? tokenSet.expires_at * 1000
          : Date.now() + 3600 * 1000,
    };
  };
}
