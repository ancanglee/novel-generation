import { Spinner } from "@novelgen/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { DataTable } from "../../components/DataTable";
import { JsonViewer } from "../../components/JsonViewer";
import { adminQk } from "../../lib/adminQueryKeys";
import { api } from "../../lib/api";

interface SchemaRow {
  schema_id: string;
  name: string;
  fields: string | unknown;
  version: number;
  updated_by: string;
  updated_at: string;
}

export default function SchemasPage() {
  const q = useQuery({
    queryKey: adminQk.schemas(),
    queryFn: () => api.request<{ schemas: SchemaRow[] }>("/api/v1/admin/analysis-schemas"),
  });
  const [selected, setSelected] = useState<SchemaRow | null>(null);

  return (
    <div className="grid h-[calc(100vh-3.5rem)] grid-cols-[1fr_24rem]">
      <div className="space-y-4 overflow-y-auto p-6">
        <h1 className="text-2xl font-semibold">分析模板</h1>
        {q.isLoading ? (
          <Spinner />
        ) : (
          <DataTable<SchemaRow>
            columns={[
              { key: "name", header: "名称" },
              { key: "schema_id", header: "ID" },
              { key: "version", header: "版本" },
            ]}
            rows={q.data?.schemas ?? []}
            getRowKey={(r) => r.schema_id}
            onRowClick={(r) => setSelected(r)}
            selectedKey={selected?.schema_id ?? null}
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
