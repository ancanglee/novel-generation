import { useQuery } from "@tanstack/react-query";
import { adminQk } from "../lib/adminQueryKeys";
import { api } from "../lib/api";

export interface AdminUserRow {
  user_id: string;
  email: string;
  display_name: string;
  team_id: string;
  global_role: string;
  team_role: string;
  status: string;
}

export function useUsersQuery(limit = 50) {
  return useQuery({
    queryKey: adminQk.users(limit),
    queryFn: () =>
      api.request<{ users: AdminUserRow[]; count: number }>("/api/v1/admin/users", {
        query: { limit },
      }),
    staleTime: 15_000,
  });
}
