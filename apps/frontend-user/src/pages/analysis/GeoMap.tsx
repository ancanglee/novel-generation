import { Spinner } from "@novelgen/ui";
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { api } from "../../lib/api";

const ReactECharts = lazy(() => import("echarts-for-react"));

interface PlaceDto {
  place_id: string;
  name: string;
  x?: number;
  y?: number;
  mentions: number;
}

interface RouteDto {
  from: string;
  to: string;
  character_id: string;
}

interface GeoPayload {
  places: PlaceDto[];
  routes: RouteDto[];
}

export default function GeoMap({ novelId }: { novelId: string }) {
  const { data, isLoading } = useQuery({
    enabled: Boolean(novelId),
    queryKey: ["novels", novelId, "geo"] as const,
    queryFn: () => api.request<GeoPayload>(`/api/v1/novels/${novelId}/geo`),
  });

  if (isLoading || !data) {
    return <div className="flex h-48 items-center justify-center"><Spinner /></div>;
  }

  const points = data.places.map((p) => ({
    name: p.name,
    value: [p.x ?? 0, p.y ?? 0, p.mentions],
  }));

  const option = {
    xAxis: { type: "value", name: "x", show: true },
    yAxis: { type: "value", name: "y", show: true },
    tooltip: { trigger: "item", formatter: (p: unknown) => {
      const d = p as { name: string; value: number[] };
      return `${d.name}<br/>提及 ${d.value[2]} 次`;
    } },
    series: [
      {
        type: "scatter",
        symbolSize: (v: number[]) => Math.max(8, Math.sqrt(v[2]) * 4),
        data: points,
        label: { show: true, formatter: "{b}", fontSize: 10 },
      },
    ],
  };

  return (
    <div className="h-[60vh] rounded-lg border bg-card">
      <Suspense fallback={<div className="flex h-full items-center justify-center"><Spinner /></div>}>
        <ReactECharts option={option} style={{ height: "100%", width: "100%" }} notMerge />
      </Suspense>
    </div>
  );
}
