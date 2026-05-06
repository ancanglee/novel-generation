import { lazy, Suspense } from "react";
import { Spinner } from "@novelgen/ui";
import type { MonitoringSummary } from "../../../hooks/useMonitoringQuery";

const ReactECharts = lazy(() => import("echarts-for-react"));

export default function LatencyChart({ summary }: { summary: MonitoringSummary }) {
  const stages = ["ingestion", "analysis", "chapter", "critic", "consistency"] as const;
  const values = stages.map((s) => summary.latency[`${s}_p95_ms` as const] ?? 0);
  const option = {
    title: { text: "关键阶段 P95 延迟 (ms)", left: "left", textStyle: { fontSize: 14 } },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: ["采集", "分析", "章节", "评审", "一致性"] },
    yAxis: { type: "value" },
    series: [{ type: "bar", data: values, itemStyle: { color: "#0ea5e9" } }],
  };
  return (
    <div className="h-64 rounded-lg border bg-card p-4">
      <Suspense fallback={<Spinner />}>
        <ReactECharts option={option} style={{ height: "100%", width: "100%" }} notMerge />
      </Suspense>
    </div>
  );
}
