import fastifyCookie from "@fastify/cookie";
import fastifyCors from "@fastify/cors";
import Fastify from "fastify";
import { Issuer, generators } from "openid-client";
import { loadConfig } from "./config.js";
import { authRoutes, refreshTokensFactory } from "./routes/auth.js";
import { healthRoutes } from "./routes/health.js";
import { proxyRoutes } from "./routes/proxy.js";
import { telemetryRoutes } from "./routes/telemetry.js";
import { csrfGuard } from "./security/csrf.js";
import { registerHelmet } from "./security/helmet.js";
import { registerRateLimit } from "./security/rateLimit.js";
import { createCookieSigner } from "./session/cookies.js";
import { sessionMiddleware } from "./session/middleware.js";
import { createSessionStore } from "./session/store.js";
import { createEmfWriter } from "./telemetry/emf.js";

export async function buildApp() {
  const config = loadConfig();

  const app = Fastify({
    logger: { level: config.LOG_LEVEL },
    genReqId: () => crypto.randomUUID(),
    trustProxy: true,
  });

  await registerHelmet(app, config);
  await app.register(fastifyCors, {
    origin: [config.APP_BASE_URL],
    credentials: true,
  });
  await app.register(fastifyCookie);
  await registerRateLimit(app);

  const signer = createCookieSigner(config.SESSION_SIGNING_KEY);
  const store = createSessionStore({
    ttlMs: config.SESSION_TTL_HOURS * 3600 * 1000,
    maxEntries: 5000,
  });

  const issuer = await Issuer.discover(config.cognitoIssuerUrl);
  const oidcClient = new issuer.Client({
    client_id: config.COGNITO_APP_CLIENT_ID,
    client_secret: config.COGNITO_CLIENT_SECRET,
    redirect_uris: [config.redirectUri],
    response_types: ["code"],
    token_endpoint_auth_method: config.COGNITO_CLIENT_SECRET ? "client_secret_post" : "none",
  });
  const refreshTokens = await refreshTokensFactory(oidcClient);

  app.addHook("preHandler", sessionMiddleware({ config, store, signer, refreshTokens }));
  app.addHook("preHandler", csrfGuard);

  const writeMetric = createEmfWriter({ logger: app.log, env: config.NOVELGEN_ENV });

  await healthRoutes(app, { store });
  await authRoutes(app, { config, signer, store, oidcClient, generators });
  await telemetryRoutes(app, { write: writeMetric });
  await proxyRoutes(app, { config });

  return { app, config };
}

async function main(): Promise<void> {
  const { app, config } = await buildApp();
  const address = await app.listen({ host: "0.0.0.0", port: config.PORT });
  app.log.info({ address, env: config.NOVELGEN_ENV }, "bff_started");

  const shutdown = async (signal: NodeJS.Signals): Promise<void> => {
    app.log.info({ signal }, "bff_shutting_down");
    await app.close();
    process.exit(0);
  };
  process.once("SIGTERM", shutdown);
  process.once("SIGINT", shutdown);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
