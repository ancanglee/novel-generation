import type { ApiError as ApiErrorBody } from "@novelgen/types";

export class ApiClientError extends Error {
  public readonly status: number;
  public readonly code: string;
  public readonly body: ApiErrorBody | null;
  public readonly upstreamError: string | null;

  constructor(
    status: number,
    code: string,
    message: string,
    body: ApiErrorBody | null,
    upstreamError: string | null,
  ) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.body = body;
    this.upstreamError = upstreamError;
  }
}

export class ApiAuthError extends ApiClientError {
  constructor(body: ApiErrorBody | null, upstreamError: string | null) {
    super(401, "UNAUTHENTICATED", "Session expired — please sign in again", body, upstreamError);
    this.name = "ApiAuthError";
  }
}

export class ApiConflictFrozenError extends ApiClientError {
  constructor(body: ApiErrorBody | null) {
    super(409, "CONFLICT_REWRITE_FROZEN", "多次尝试未能解决，请手动编辑", body, null);
    this.name = "ApiConflictFrozenError";
  }
}
