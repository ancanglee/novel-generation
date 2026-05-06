import { useQuery } from "@tanstack/react-query";
import { adminQk } from "../lib/adminQueryKeys";
import { api } from "../lib/api";

export interface ModelEntry {
  model_id: string;
  max_output_tokens: number;
  temperature: number;
  top_p?: number;
}

export interface ModelConfigRow {
  stage: string;
  primary: ModelEntry;
  fallback: ModelEntry | null;
  version: number;
  updated_by: string;
  updated_at: string;
}

export function useModelConfigsQuery() {
  return useQuery({
    queryKey: adminQk.modelConfigs(),
    queryFn: () => api.request<{ stages: ModelConfigRow[] }>("/api/v1/admin/model-configs"),
    staleTime: 30_000,
  });
}
