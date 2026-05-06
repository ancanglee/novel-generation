import { Button, Spinner, Toast } from "@novelgen/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { adminQk } from "../../lib/adminQueryKeys";

interface ConcurrencyRow {
  deep_read_default: number;
  deep_read_max: number;
  chapter_parallel_max: number;
  updated_by?: string | null;
  updated_at?: string | null;
}

export default function ConcurrencyPage() {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: adminQk.concurrency(),
    queryFn: () => api.request<ConcurrencyRow>("/api/v1/admin/concurrency"),
  });
  const [draft, setDraft] = useState<ConcurrencyRow | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (q.data && !draft) setDraft(q.data);
  }, [q.data, draft]);

  const save = useMutation({
    mutationFn: () =>
      api.request("/api/v1/admin/concurrency", {
        method: "PUT",
        body: {
          deep_read_default: draft?.deep_read_default,
          deep_read_max: draft?.deep_read_max,
          chapter_parallel_max: draft?.chapter_parallel_max,
        },
      }),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: adminQk.concurrency() });
    },
    onError: () => setError("保存失败，请稍后重试"),
  });

  if (q.isLoading || !draft) return <Spinner />;

  return (
    <div className="mx-auto max-w-xl space-y-4 p-6">
      <h1 className="text-2xl font-semibold">并发配置</h1>
      <Field label="深读默认" value={draft.deep_read_default} min={1} max={64}
        onChange={(v) => setDraft({ ...draft, deep_read_default: v })} />
      <Field label="深读最大" value={draft.deep_read_max} min={1} max={128}
        onChange={(v) => setDraft({ ...draft, deep_read_max: v })} />
      <Field label="章节并行最大" value={draft.chapter_parallel_max} min={1} max={4}
        onChange={(v) => setDraft({ ...draft, chapter_parallel_max: v })} />
      <Button loading={save.isPending} onClick={() => save.mutate()}>保存</Button>
      {error ? <Toast variant="error" title="保存失败" description={error} /> : null}
    </div>
  );
}

function Field({ label, value, min, max, onChange }: {
  label: string; value: number; min: number; max: number;
  onChange(v: number): void;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-muted-foreground">{label}（{min}-{max}）</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number.parseInt(e.target.value, 10))}
        className="h-9 w-full rounded-md border px-2 text-sm"
      />
    </label>
  );
}
