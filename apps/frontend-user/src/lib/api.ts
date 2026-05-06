import { ApiClient } from "@novelgen/api-client";
import { useSessionStore } from "../stores/sessionStore";
import { getCsrfToken } from "./csrf";

export const api = new ApiClient({
  getCsrfToken,
  onUnauthenticated: () => {
    useSessionStore.getState().clear();
    if (!location.pathname.startsWith("/auth/")) {
      location.href = "/auth/login";
    }
  },
});
