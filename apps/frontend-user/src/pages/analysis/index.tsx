import { CharacterGraph, Spinner, StyleRadar } from "@novelgen/ui";
import { useQuery } from "@tanstack/react-query";
import { Suspense, lazy, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { qk } from "../../lib/queryKeys";

const GeoMap = lazy(() => import("./GeoMap"));

interface CharacterGraphDto {
  nodes: { id: string; name: string; role?: string }[];
  edges: { id: string; source: string; target: string; relation: string }[];
}

interface StyleDto {
  tone: number;
  pace: number;
  detail_density: number;
  dialogue_ratio: number;
  emotion_intensity: number;
  scope: number;
}

interface AnalysisReportDto {
  classification: { genre: string; sub_genres: string[]; tags: string[] };
  summary: string;
}

type Tab = "overview" | "characters" | "map" | "style";

export default function AnalysisPage() {
  const { novelId } = useParams();
  const [tab, setTab] = useState<Tab>("overview");

  const analysis = useQuery({
    enabled: Boolean(novelId),
    queryKey: novelId ? qk.analysis(novelId) : ["analysis", "none"],
    queryFn: () => api.request<AnalysisReportDto>(`/api/v1/novels/${novelId}/analysis`),
  });
  const characters = useQuery({
    enabled: Boolean(novelId) && tab === "characters",
    queryKey: novelId ? qk.characters(novelId) : ["characters", "none"],
    queryFn: () => api.request<CharacterGraphDto>(`/api/v1/novels/${novelId}/characters`),
  });
  const style = useQuery({
    enabled: Boolean(novelId) && tab === "style",
    queryKey: novelId ? qk.style(novelId) : ["style", "none"],
    queryFn: () => api.request<StyleDto>(`/api/v1/novels/${novelId}/style`),
  });

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <h1 className="text-2xl font-semibold">分析报告</h1>

      <nav className="flex gap-2 border-b">
        {(["overview", "characters", "map", "style"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm ${
              tab === t ? "border-b-2 border-primary" : "text-muted-foreground"
            }`}
          >
            {t === "overview"
              ? "概览"
              : t === "characters"
                ? "人物关系"
                : t === "map"
                  ? "地图"
                  : "风格"}
          </button>
        ))}
      </nav>

      {tab === "overview" ? (
        analysis.isLoading ? (
          <Spinner />
        ) : (
          <div className="space-y-4">
            <div className="rounded-lg border bg-card p-4">
              <p className="text-sm text-muted-foreground">分类</p>
              <p className="mt-1 text-lg font-medium">
                {analysis.data?.classification.genre ?? "—"}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {analysis.data?.classification.tags?.join(" · ")}
              </p>
            </div>
            <div className="rounded-lg border bg-card p-4">
              <p className="text-sm text-muted-foreground">摘要</p>
              <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed">
                {analysis.data?.summary ?? "—"}
              </p>
            </div>
          </div>
        )
      ) : null}

      {tab === "characters" ? (
        <div className="h-[60vh] rounded-lg border bg-card">
          {characters.isLoading ? (
            <div className="flex h-full items-center justify-center">
              <Spinner />
            </div>
          ) : (
            <CharacterGraph
              nodes={characters.data?.nodes ?? []}
              edges={characters.data?.edges ?? []}
            />
          )}
        </div>
      ) : null}

      {tab === "map" ? (
        <Suspense
          fallback={
            <div className="flex h-48 items-center justify-center">
              <Spinner />
            </div>
          }
        >
          <GeoMap novelId={novelId ?? ""} />
        </Suspense>
      ) : null}

      {tab === "style" ? (
        style.isLoading || !style.data ? (
          <Spinner />
        ) : (
          <StyleRadar vector={style.data} />
        )
      ) : null}
    </div>
  );
}
