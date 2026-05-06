import { Spinner } from "@novelgen/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { DataTable } from "../../components/DataTable";
import { JsonViewer } from "../../components/JsonViewer";
import { adminQk } from "../../lib/adminQueryKeys";
import { api } from "../../lib/api";

interface TemplateRow {
  template_id: string;
  name: string;
  description: string;
  default_chapter_count: number;
  version: number;
}

export default function TemplatesPage() {
  const q = useQuery({
    queryKey: adminQk.templates(),
    queryFn: () => api.request<{ templates: TemplateRow[] }>("/api/v1/admin/outline-templates"),
  });
  const [selected, setSelected] = useState<TemplateRow | null>(null);

  return (
    <div className="grid h-[calc(100vh-3.5rem)] grid-cols-[1fr_24rem]">
      <div className="space-y-4 overflow-y-auto p-6">
        <h1 className="text-2xl font-semibold">大纲模板</h1>
        {q.isLoading ? (
          <Spinner />
        ) : (
          <DataTable<TemplateRow>
            columns={[
              { key: "name", header: "名称" },
              { key: "template_id", header: "ID" },
              { key: "default_chapter_count", header: "默认章数" },
              { key: "version", header: "版本" },
            ]}
            rows={q.data?.templates ?? []}
            getRowKey={(r) => r.template_id}
            onRowClick={(r) => setSelected(r)}
            selectedKey={selected?.template_id ?? null}
          />
        )}
      </div>
      <aside className="border-l overflow-y-auto p-4">
        <h2 className="mb-2 text-sm font-semibold">详情</h2>
        {selected ? (
          <JsonViewer value={selected} />
        ) : (
          <p className="text-sm text-muted-foreground">点击行查看详情</p>
        )}
      </aside>
    </div>
  );
}
