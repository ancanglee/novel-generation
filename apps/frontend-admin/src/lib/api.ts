import { ApiClient } from "@novelgen/api-client";
import { useAdminSessionStore } from "../stores/adminSessionStore";

function getCsrfToken(): string {
  const match = /(?:^|;\s*)csrf=([^;]+)/.exec(document.cookie);
  const val = match?.[1];
  return val ? decodeURIComponent(val) : "";
}

export const api = new ApiClient({
  getCsrfToken,
  onUnauthenticated: () => {
    useAdminSessionStore.getState().clear();
    if (!location.pathname.startsWith("/auth/")) {
      location.href = "/auth/login";
    }
  },
});
