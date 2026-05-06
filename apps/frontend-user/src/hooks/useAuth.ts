import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "../lib/api";
import { qk } from "../lib/queryKeys";
import { type Principal, useSessionStore } from "../stores/sessionStore";

interface MeResponse {
  principal: Principal;
  csrf: string;
}

export function useAuth() {
  const setPrincipal = useSessionStore((s) => s.setPrincipal);
  const markReady = useSessionStore((s) => s.markReady);

  const query = useQuery({
    queryKey: qk.auth(),
    queryFn: () => api.request<MeResponse>("/auth/me"),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  useEffect(() => {
    if (query.isSuccess && query.data) {
      setPrincipal(query.data.principal, query.data.csrf);
      markReady();
    } else if (query.isError) {
      setPrincipal(null, null);
      markReady();
    }
  }, [query.isSuccess, query.isError, query.data, setPrincipal, markReady]);

  return query;
}
