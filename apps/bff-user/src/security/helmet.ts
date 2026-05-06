import fastifyHelmet from "@fastify/helmet";
import type { FastifyInstance } from "fastify";
import type { AppConfig } from "../config";

export async function registerHelmet(app: FastifyInstance, config: AppConfig): Promise<void> {
  await app.register(fastifyHelmet, {
    contentSecurityPolicy: {
      directives: {
        defaultSrc: ["'self'"],
        scriptSrc: ["'self'", "'wasm-unsafe-eval'"],
        styleSrc: ["'self'", "'unsafe-inline'"],
        imgSrc: ["'self'", "data:", `https://s3.${config.COGNITO_REGION}.amazonaws.com`],
        connectSrc: [
          "'self'",
          `https://cognito-idp.${config.COGNITO_REGION}.amazonaws.com`,
          `https://${config.COGNITO_DOMAIN}`,
        ],
        fontSrc: ["'self'", "data:"],
        frameAncestors: ["'none'"],
      },
    },
    referrerPolicy: { policy: "same-origin" },
    crossOriginEmbedderPolicy: false,
  });
}
