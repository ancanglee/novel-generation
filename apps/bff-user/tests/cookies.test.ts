import { describe, expect, it } from "vitest";
import { createCookieSigner } from "../src/session/cookies";

describe("CookieSigner", () => {
  it("signs and verifies a value", () => {
    const signer = createCookieSigner("12345678901234567890123456789012");
    const signed = signer.sign("session-id-xyz");
    expect(signer.verify(signed)).toBe("session-id-xyz");
  });

  it("rejects tampered values", () => {
    const signer = createCookieSigner("12345678901234567890123456789012");
    const signed = signer.sign("abc");
    const tampered = `xyz.${signed.split(".")[1]}`;
    expect(signer.verify(tampered)).toBeNull();
  });

  it("rejects malformed input", () => {
    const signer = createCookieSigner("12345678901234567890123456789012");
    expect(signer.verify("no-separator")).toBeNull();
    expect(signer.verify(".bar")).toBeNull();
    expect(signer.verify("")).toBeNull();
  });

  it("uses different signatures for different keys", () => {
    const a = createCookieSigner("a".repeat(32));
    const b = createCookieSigner("b".repeat(32));
    const signed = a.sign("x");
    expect(b.verify(signed)).toBeNull();
  });
});
