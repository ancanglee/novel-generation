import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { qk } from "../lib/queryKeys";

export interface JobDto {
  job_id: string;
  status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELED";
  progress: number;
  result_ref?: string | null;
  error_message?: string | null;
}

const IN_PROGRESS: JobDto["status"][] = ["QUEUED", "RUNNING"];

export function useJobPoll(jobId: string | null | undefined) {
  return useQuery({
    enabled: Boolean(jobId),
    queryKey: jobId ? qk.job(jobId) : ["jobs", "none"],
    queryFn: () => api.request<JobDto>(`/api/v1/jobs/${jobId}`),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return status && IN_PROGRESS.includes(status) ? 2000 : false;
    },
    refetchIntervalInBackground: false,
  });
}
