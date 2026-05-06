import { useQuery } from "@tanstack/react-query";
import { adminQk } from "../lib/adminQueryKeys";
import { api } from "../lib/api";

export interface MonitoringSummary {
  period: { from: string; to: string };
  totals: {
    generations_started: number;
    generations_succeeded: number;
    generations_failed: number;
  };
  latency: {
    ingestion_p95_ms: number;
    analysis_p95_ms: number;
    chapter_p95_ms: number;
    critic_p95_ms: number;
    consistency_p95_ms: number;
  };
  sse_ttft_p95_ms: number;
  error_rate_percent: number;
  cache_hit?: boolean;
}

export function useMonitoringQuery(from: string, to: string) {
  return useQuery({
    queryKey: adminQk.monitoring(from, to),
    queryFn: () =>
      api.request<MonitoringSummary>("/api/v1/admin/monitoring/summary", {
        query: { from, to },
      }),
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  });
}
