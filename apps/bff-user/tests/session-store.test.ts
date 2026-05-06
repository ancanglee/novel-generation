import { describe, expect, it, vi } from "vitest";
import { createSessionStore } from "../src/session/store";

function makeSession(id: string) {
  return {
    id,
    idToken: "id",
    accessToken: "access",
    refreshToken: "refresh",
    expiresAt: Date.now() + 3_600_000,
    csrfToken: "csrf",
    createdAt: Date.now(),
    lastSeenAt: Date.now(),
    principal: {
      userId: "u",
      teamId: "t",
      email: "a@b",
      globalRole: "regular_user",
      teamRole: "member",
    },
  };
}

describe("createSessionStore", () => {
  it("stores, reads and deletes sessions", () => {
    const store = createSessionStore({ ttlMs: 1_000_000, maxEntries: 10 });
    const s = makeSession("sid-1");
    store.set(s);
    expect(store.get("sid-1")?.principal.userId).toBe("u");
    store.delete("sid-1");
    expect(store.get("sid-1")).toBeUndefined();
  });

  it("updates lastSeenAt on get", async () => {
    vi.useFakeTimers();
    const store = createSessionStore({ ttlMs: 1_000_000, maxEntries: 10 });
    const s = makeSession("sid-2");
    store.set(s);
    const t0 = s.lastSeenAt;
    vi.advanceTimersByTime(5000);
    const later = store.get("sid-2");
    expect(later?.lastSeenAt).toBeGreaterThan(t0);
    vi.useRealTimers();
  });

  it("evicts beyond max entries", () => {
    const store = createSessionStore({ ttlMs: 1_000_000, maxEntries: 3 });
    for (let i = 0; i < 5; i++) store.set(makeSession(`s${i}`));
    expect(store.size()).toBe(3);
  });
});
