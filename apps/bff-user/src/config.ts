import { z } from "zod";

const envSchema = z.object({
  NOVELGEN_ENV: z.enum(["dev", "stage", "prod"]).default("dev"),
  PORT: z.coerce.number().int().positive().default(3000),
  API_BASE_URL: z.string().url(),
  COGNITO_USER_POOL_ID: z.string().min(1),
  COGNITO_APP_CLIENT_ID: z.string().min(1),
  COGNITO_DOMAIN: z.string().min(1),
  COGNITO_REGION: z.string().min(1).default("us-east-1"),
  COGNITO_CLIENT_SECRET: z.string().optional(),
  APP_BASE_URL: z.string().url(),
  SESSION_SIGNING_KEY: z.string().min(32),
  SESSION_TTL_HOURS: z.coerce.number().positive().default(6),
  LOG_LEVEL: z.preprocess(
    (v) => (typeof v === "string" ? v.toLowerCase() : v),
    z.enum(["fatal", "error", "warn", "info", "debug", "trace"]).default("info"),
  ),
});

export type AppConfig = z.infer<typeof envSchema> & {
  cognitoIssuerUrl: string;
  redirectUri: string;
  logoutUri: string;
};

let cached: AppConfig | undefined;

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AppConfig {
  if (cached) return cached;
  const parsed = envSchema.parse(env);
  cached = {
    ...parsed,
    cognitoIssuerUrl: `https://cognito-idp.${parsed.COGNITO_REGION}.amazonaws.com/${parsed.COGNITO_USER_POOL_ID}`,
    redirectUri: `${parsed.APP_BASE_URL.replace(/\/$/, "")}/auth/callback`,
    logoutUri: `${parsed.APP_BASE_URL.replace(/\/$/, "")}/`,
  };
  return cached;
}
