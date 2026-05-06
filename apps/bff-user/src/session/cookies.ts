import { createHmac, timingSafeEqual } from "node:crypto";

const SEPARATOR = ".";

export interface CookieSigner {
  sign(value: string): string;
  verify(signed: string): string | null;
}

export function createCookieSigner(key: string): CookieSigner {
  if (!key) throw new Error("SESSION_SIGNING_KEY is required");
  return {
    sign(value: string): string {
      const mac = createHmac("sha256", key).update(value).digest("base64url");
      return `${value}${SEPARATOR}${mac}`;
    },
    verify(signed: string): string | null {
      const idx = signed.lastIndexOf(SEPARATOR);
      if (idx < 1) return null;
      const value = signed.slice(0, idx);
      const mac = signed.slice(idx + 1);
      const expected = createHmac("sha256", key).update(value).digest("base64url");
      const a = Buffer.from(mac);
      const b = Buffer.from(expected);
      if (a.length !== b.length) return null;
      return timingSafeEqual(a, b) ? value : null;
    },
  };
}
