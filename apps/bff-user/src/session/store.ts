import { LRUCache } from "lru-cache";

export interface PrincipalSummary {
  userId: string;
  teamId: string;
  email: string;
  globalRole: string;
  teamRole: string;
}

export interface ServerSession {
  id: string;
  idToken: string;
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // epoch ms
  principal: PrincipalSummary;
  csrfToken: string;
  createdAt: number;
  lastSeenAt: number;
}

export interface SessionStoreOptions {
  ttlMs: number;
  maxEntries: number;
}

export interface SessionStore {
  get(id: string): ServerSession | undefined;
  set(session: ServerSession): void;
  delete(id: string): void;
  size(): number;
}

export function createSessionStore(options: SessionStoreOptions): SessionStore {
  const cache = new LRUCache<string, ServerSession>({
    max: options.maxEntries,
    ttl: options.ttlMs,
    updateAgeOnGet: true,
  });
  return {
    get: (id) => {
      const s = cache.get(id);
      if (s) s.lastSeenAt = Date.now();
      return s;
    },
    set: (session) => {
      cache.set(session.id, session);
    },
    delete: (id) => {
      cache.delete(id);
    },
    size: () => cache.size,
  };
}
