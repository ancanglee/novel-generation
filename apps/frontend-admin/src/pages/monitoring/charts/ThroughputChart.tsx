import { Spinner } from "@novelgen/ui";
import { Suspense, lazy } from "react";
import type { MonitoringSummary } from "../../../hooks/useMonitoringQuery";

const ReactECharts = lazy(() => import("echarts-for-react"));

export default function ThroughputChart({ summary }: { summary: MonitoringSummary }) {
  const option = {
    title: { text: "生成任务吞吐", left: "left", textStyle: { fontSize: 14 } },
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, data: ["启动", "成功", "失败"] },
    xAxis: { type: "category", data: ["当前周期"] },
    yAxis: { type: "value" },
    series: [
      { name: "启动", type: "bar", stack: "t", data: [summary.totals.generations_started] },
      { name: "成功", type: "bar", stack: "t", data: [summary.totals.generations_succeeded] },
      {
        name: "失败",
        type: "bar",
        stack: "t",
        data: [summary.totals.generations_failed],
        itemStyle: { color: "#e11d48" },
      },
    ],
  };
  return (
    <div className="h-64 rounded-lg border bg-card p-4">
      <Suspense fallback={<Spinner />}>
        <ReactECharts option={option} style={{ height: "100%", width: "100%" }} notMerge />
      </Suspense>
    </div>
  );
}
