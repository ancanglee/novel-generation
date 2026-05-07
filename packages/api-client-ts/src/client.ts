// Typed fetch client that talks to BFF (which reverse-proxies to ApiService).
// Handles: CSRF, 401 redirect, upstream-error header surfacing, and JSON parsing.

import type { ApiError as ApiErrorBody } from "@novelgen/types";
import { ApiAuthError, ApiClientError, ApiConflictFrozenError } from "./errors";

export interface ApiClientOptions {
  baseUrl?: string; // defaults to '' (same origin — BFF)
  getCsrfToken: () => string;
  onUnauthenticated?: () => void; // triggered on 401
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  body?: unknown;
  query?: Record<string, string | number | undefined>;
  signal?: AbortSignal;
  teamId?: string;
  /** When true, do not JSON-parse the response body; return raw Response. */
  raw?: boolean;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly getCsrfToken: () => string;
  private readonly onUnauthenticated?: () => void;

  constructor(options: ApiClientOptions) {
    this.baseUrl = options.baseUrl ?? "";
    this.getCsrfToken = options.getCsrfToken;
    this.onUnauthenticated = options.onUnauthenticated;
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const url = new URL(this.baseUrl + path, window.location.origin);
    if (options.query) {
      for (const [k, v] of Object.entries(options.query)) {
        if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
      }
    }
    const method = options.method ?? "GET";
    const headers = new Headers({ Accept: "application/json" });
    if (options.body !== undefined) headers.set("Content-Type", "application/json");
    if (method !== "GET") headers.set("X-CSRF-Token", this.getCsrfToken());
    if (options.teamId) headers.set("X-Team-Id", options.teamId);

    const resp = await fetch(url.toString(), {
      method,
      credentials: "include",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });

    if (resp.status === 401) {
      this.onUnauthenticated?.();
      throw new ApiAuthError(await this.safeJson(resp), resp.headers.get("x-upstream-error"));
    }

    if (!resp.ok) {
      const body = await this.safeJson(resp);
      const code = body?.error?.code ?? `HTTP_${resp.status}`;
      const message = body?.error?.message ?? resp.statusText;
      const upstream = resp.headers.get("x-upstream-error");
      if (resp.status === 409 && code === "CONFLICT_REWRITE_FROZEN") {
        throw new ApiConflictFrozenError(body);
      }
      throw new ApiClientError(resp.status, code, message, body, upstream);
    }

    if (options.raw) return resp as unknown as T;
    if (resp.status === 204) return undefined as T;
    return (await resp.json()) as T;
  }

  private async safeJson(resp: Response): Promise<ApiErrorBody | null> {
    try {
      return (await resp.json()) as ApiErrorBody;
    } catch {
      return null;
    }
  }
}

/** Factory with sensible defaults: read CSRF from cookie, redirect to /auth/login on 401. */
export function createDefaultClient(): ApiClient {
  return new ApiClient({
    getCsrfToken: () => {
      const match = /(?:^|;\s*)csrf=([^;]+)/.exec(document.cookie);
      const val = match?.[1];
      return val ? decodeURIComponent(val) : "";
    },
    onUnauthenticated: () => {
      if (!window.location.pathname.startsWith("/auth/")) {
        window.location.href = "/auth/login";
      }
    },
  });
}
