import { Badge, Button, Spinner } from "@novelgen/ui";
import { useState } from "react";
import { DataTable } from "../../components/DataTable";
import { type ModelConfigRow, useModelConfigsQuery } from "../../hooks/useModelConfigsQuery";
import { admin } from "../../strings/admin";
import { EditModelModal } from "./EditModelModal";

export default function ModelConfigsPage() {
  const q = useModelConfigsQuery();
  const [editing, setEditing] = useState<ModelConfigRow | null>(null);

  return (
    <div className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">{admin.nav.modelConfigs}</h1>
      <p className="text-sm text-muted-foreground">
        为 9 个任务阶段独立配置 Claude 模型。保存后生效时间约 60 秒。
      </p>
      {q.isLoading ? <Spinner /> : (
        <DataTable<ModelConfigRow>
          columns={[
            { key: "stage", header: "阶段", render: (r) => <Badge>{admin.stages[r.stage as keyof typeof admin.stages] ?? r.stage}</Badge> },
            { key: "primary", header: "主模型", render: (r) => r.primary.model_id },
            { key: "primary_params", header: "参数", render: (r) => `maxTokens=${r.primary.max_output_tokens} · temp=${r.primary.temperature}` },
            { key: "fallback", header: "降级", render: (r) => r.fallback?.model_id ?? "—" },
            { key: "version", header: "版本" },
            { key: "updated_by", header: "更新者", render: (r) => r.updated_by?.slice(0, 8) ?? "—" },
            {
              key: "actions",
              header: "操作",
              render: (r) => (
                <Button
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditing(r);
                  }}
                >
                  编辑
                </Button>
              ),
            },
          ]}
          rows={q.data?.stages ?? []}
          getRowKey={(r) => r.stage}
          onRowClick={(r) => setEditing(r)}
        />
      )}
      {editing ? (
        <EditModelModal
          row={editing}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </div>
  );
}
