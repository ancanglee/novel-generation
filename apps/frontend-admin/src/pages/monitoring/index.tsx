import { Button, Spinner } from "@novelgen/ui";
import { lazy, Suspense } from "react";
import { useMonitoringQuery } from "../../hooks/useMonitoringQuery";
import { type RangePreset, useMonitoringRangeStore } from "../../stores/monitoringRangeStore";

const ThroughputChart = lazy(() => import("./charts/ThroughputChart"));
const LatencyChart = lazy(() => import("./charts/LatencyChart"));

const PRESETS: RangePreset[] = ["1h", "24h", "7d", "30d"];

export default function MonitoringPage() {
  const { preset, from, to, set } = useMonitoringRangeStore();
  const q = useMonitoringQuery(from, to);

  return (
    <div className="space-y-4 p-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">监控</h1>
        <div className="flex items-center gap-2">
          {PRESETS.map((p) => (
            <Button
              key={p}
              size="sm"
              variant={preset === p ? "primary" : "ghost"}
              onClick={() => set(p)}
            >
              {p}
            </Button>
          ))}
          <Button size="sm" variant="secondary" onClick={() => q.refetch()}>刷新</Button>
        </div>
      </header>

      {q.isError ? (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          监控聚合暂不可用，展示上一次缓存数据
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <StatCard label="生成任务启动" value={q.data?.totals.generations_started ?? "—"} />
        <StatCard label="生成任务成功" value={q.data?.totals.generations_succeeded ?? "—"} />
        <StatCard label="生成任务失败" value={q.data?.totals.generations_failed ?? "—"} />
        <StatCard label="错误率 %" value={q.data?.error_rate_percent ?? "—"} />
        <StatCard label="SSE TTFT P95 ms" value={q.data?.sse_ttft_p95_ms ?? "—"} />
      </div>

      <Suspense fallback={<Spinner />}>
        {q.data ? <ThroughputChart summary={q.data} /> : null}
      </Suspense>
      <Suspense fallback={<Spinner />}>
        {q.data ? <LatencyChart summary={q.data} /> : null}
      </Suspense>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}
