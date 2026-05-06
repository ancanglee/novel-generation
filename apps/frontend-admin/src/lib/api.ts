import { ApiClient } from "@novelgen/api-client";
import { useAdminSessionStore } from "../stores/adminSessionStore";

function getCsrfToken(): string {
  const match = /(?:^|;\s*)csrf=([^;]+)/.exec(document.cookie);
  return match ? decodeURIComponent(match[1]) : "";
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
