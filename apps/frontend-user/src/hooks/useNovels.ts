import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { qk } from "../lib/queryKeys";

export interface NovelSummaryDto {
  novel_id: string;
  title: string;
  source_type: string;
  status: string;
  chapter_count: number;
  created_at: string;
}

export interface NovelListDto {
  items: NovelSummaryDto[];
  next_cursor?: string;
}

export function useNovels(cursor?: string) {
  return useQuery({
    queryKey: [...qk.novels(), cursor ?? ""] as const,
    queryFn: () =>
      api.request<NovelListDto>("/api/v1/novels", {
        query: cursor ? { cursor } : {},
      }),
  });
}

export function useNovel(novelId: string | undefined) {
  return useQuery({
    enabled: Boolean(novelId),
    queryKey: novelId ? qk.novel(novelId) : ["novels", "none"],
    queryFn: () =>
      api.request<NovelSummaryDto>(`/api/v1/novels/${novelId}`),
  });
}
