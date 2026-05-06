import { Badge, Button } from "@novelgen/ui";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { JobDto } from "../components/JobPoller";
import { api } from "../lib/api";
import { qk } from "../lib/queryKeys";
import { common } from "../strings";

interface DashboardSummary {
  recent_jobs: Array<JobDto & { job_type: string; subject_id: string; created_at: string }>;
  novels_count: number;
  generations_count: number;
}

export default function Dashboard() {
  const query = useQuery({
    queryKey: ["dashboard", "summary"] as const,
    queryFn: () => api.request<DashboardSummary>("/api/v1/dashboard/summary"),
    staleTime: 15_000,
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">{common.nav.dashboard}</h1>
        <p className="mt-1 text-sm text-muted-foreground">快速进入你最近的小说与生成任务</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="小说库" value={query.data?.novels_count ?? "—"} />
        <Stat label="生成任务" value={query.data?.generations_count ?? "—"} />
        <Stat label="最近状态" value={query.data?.recent_jobs?.[0]?.status ?? "—"} />
      </div>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-medium">最近任务</h2>
          <Link to="/novels">
            <Button size="sm" variant="secondary">
              {common.nav.novels}
            </Button>
          </Link>
        </div>
        <div className="rounded-lg border bg-card">
          {query.isLoading ? (
            <p className="p-4 text-sm text-muted-foreground">加载中…</p>
          ) : query.data?.recent_jobs?.length ? (
            <ul className="divide-y">
              {query.data.recent_jobs.slice(0, 8).map((j) => (
                <li key={j.job_id} className="flex items-center justify-between px-4 py-3">
                  <div>
                    <p className="text-sm font-medium">
                      {j.job_type} · {j.subject_id.slice(0, 8)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(j.created_at).toLocaleString()}
                    </p>
                  </div>
                  <Badge tone={statusTone(j.status)}>{labelFor(j.status)}</Badge>
                </li>
              ))}
            </ul>
          ) : (
            <p className="p-4 text-sm text-muted-foreground">
              暂无任务，前往{" "}
              <Link to="/novels" className="underline">
                小说库
              </Link>{" "}
              开始
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function statusTone(
  status: JobDto["status"],
): "default" | "success" | "warning" | "danger" | "info" {
  switch (status) {
    case "SUCCEEDED":
      return "success";
    case "FAILED":
      return "danger";
    case "CANCELED":
      return "default";
    case "RUNNING":
      return "info";
    default:
      return "warning";
  }
}

function labelFor(status: JobDto["status"]): string {
  return common.statuses[status.toLowerCase() as keyof typeof common.statuses] ?? status;
}
