import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { adminQk } from "../lib/adminQueryKeys";
import { api } from "../lib/api";
import { type AdminPrincipal, useAdminSessionStore } from "../stores/adminSessionStore";

interface MeResponse {
  principal: AdminPrincipal;
  csrf: string;
}

export function useAdminAuth() {
  const setPrincipal = useAdminSessionStore((s) => s.setPrincipal);
  const markReady = useAdminSessionStore((s) => s.markReady);

  const query = useQuery({
    queryKey: adminQk.me(),
    queryFn: () => api.request<MeResponse>("/auth/me"),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (query.isSuccess && query.data) {
      setPrincipal(query.data.principal);
      markReady();
    } else if (query.isError) {
      setPrincipal(null);
      markReady();
    }
  }, [query.isSuccess, query.isError, query.data, setPrincipal, markReady]);

  return query;
}
