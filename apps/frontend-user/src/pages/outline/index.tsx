import { Button, Spinner } from "@novelgen/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "../../components/Toast";
import { api } from "../../lib/api";
import { qk } from "../../lib/queryKeys";

interface OutlineItemDto {
  chapter_idx: number;
  title: string;
  summary: string;
  key_beats?: string[];
}

interface OutlineDto {
  items: OutlineItemDto[];
  reviewed: boolean;
  advice?: Array<{ level: "info" | "warn"; message: string }>;
}

export default function OutlinePage() {
  const { gid } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [draft, setDraft] = useState<OutlineItemDto[] | null>(null);

  const outline = useQuery({
    enabled: Boolean(gid),
    queryKey: gid ? qk.outline(gid) : ["outline", "none"],
    queryFn: () => api.request<OutlineDto>(`/api/v1/generations/${gid}/outline`),
  });

  const approve = useMutation({
    mutationFn: () =>
      api.request<{ generation_id: string }>(`/api/v1/generations/${gid}/approve-outline`, {
        method: "POST",
        body: { items: draft ?? outline.data?.items ?? [] },
      }),
    onSuccess: () =>
      api.request(`/api/v1/generations/${gid}/start`, { method: "POST" }).then(() => {
        toast({ variant: "success", title: "大纲已批准，开始生成第 1 章" });
        qc.invalidateQueries({ queryKey: qk.generation(gid!) });
        navigate(`/generations/${gid}/chapters/1`);
      }),
  });

  if (outline.isLoading || !outline.data) {
    return (
      <div className="p-8 flex items-center gap-2">
        <Spinner /> 加载大纲…
      </div>
    );
  }

  const items = draft ?? outline.data.items;

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-6">
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">大纲审阅</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            共 {items.length} 章；inline 编辑摘要，批准后开始生成
          </p>
        </div>
        <Button
          onClick={() => approve.mutate()}
          loading={approve.isPending}
          disabled={items.length === 0}
        >
          批准并开始生成
        </Button>
      </header>

      {outline.data.advice?.length ? (
        <div className="rounded-md border bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <p className="font-medium">AI 建议</p>
          <ul className="mt-1 list-disc pl-5">
            {outline.data.advice.map((a, i) => (
              <li key={i}>{a.message}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <ol className="space-y-3">
        {items.map((it, idx) => (
          <li key={it.chapter_idx} className="rounded-lg border bg-card p-3">
            <p className="text-xs text-muted-foreground">第 {it.chapter_idx} 章</p>
            <input
              value={it.title}
              onChange={(e) => {
                const next = [...items];
                next[idx] = { ...it, title: e.target.value };
                setDraft(next);
              }}
              className="mt-1 w-full border-b bg-transparent text-base font-medium outline-none"
            />
            <textarea
              value={it.summary}
              onChange={(e) => {
                const next = [...items];
                next[idx] = { ...it, summary: e.target.value };
                setDraft(next);
              }}
              rows={3}
              className="mt-2 w-full resize-y rounded-md border p-2 text-sm"
            />
          </li>
        ))}
      </ol>
    </div>
  );
}
