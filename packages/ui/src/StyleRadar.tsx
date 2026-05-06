import { lazy, Suspense } from "react";
import { Spinner } from "./primitives/Spinner";

// echarts-for-react pulls in echarts core — keep it in the analysis chunk.
const ReactECharts = lazy(() => import("echarts-for-react"));

export interface StyleVectorInput {
  tone: number;
  pace: number;
  detail_density: number;
  dialogue_ratio: number;
  emotion_intensity: number;
  scope: number;
}

export interface StyleRadarProps {
  vector: StyleVectorInput;
  referenceVector?: StyleVectorInput;
  title?: string;
  height?: number;
}

const DIMS: { key: keyof StyleVectorInput; label: string }[] = [
  { key: "tone", label: "情感色调" },
  { key: "pace", label: "节奏" },
  { key: "detail_density", label: "细节密度" },
  { key: "dialogue_ratio", label: "对白比例" },
  { key: "emotion_intensity", label: "情感强度" },
  { key: "scope", label: "视野广度" },
];

export function StyleRadar({
  vector,
  referenceVector,
  title = "风格雷达",
  height = 320,
}: StyleRadarProps) {
  const option = {
    title: { text: title, left: "center", textStyle: { fontSize: 14 } },
    tooltip: { trigger: "item" },
    legend: {
      bottom: 0,
      data: referenceVector ? ["当前", "参考"] : ["当前"],
      textStyle: { fontSize: 12 },
    },
    radar: {
      indicator: DIMS.map((d) => ({ name: d.label, max: 100 })),
      splitNumber: 5,
      axisName: { fontSize: 12 },
    },
    series: [
      {
        type: "radar",
        data: [
          {
            name: "当前",
            value: DIMS.map((d) => vector[d.key]),
            areaStyle: { opacity: 0.25 },
          },
          ...(referenceVector
            ? [
                {
                  name: "参考",
                  value: DIMS.map((d) => referenceVector[d.key]),
                  lineStyle: { type: "dashed" as const },
                },
              ]
            : []),
        ],
      },
    ],
  };

  return (
    <div style={{ height }}>
      <Suspense fallback={<div className="flex h-full items-center justify-center"><Spinner /></div>}>
        <ReactECharts option={option} style={{ height: "100%", width: "100%" }} notMerge lazyUpdate />
      </Suspense>
    </div>
  );
}
