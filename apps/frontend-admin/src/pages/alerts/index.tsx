import { Badge, Spinner } from "@novelgen/ui";
import { useQuery } from "@tanstack/react-query";
import { DataTable } from "../../components/DataTable";
import { adminQk } from "../../lib/adminQueryKeys";
import { api } from "../../lib/api";

interface AlertRow {
  rule_id: string;
  metric: string;
  threshold: number;
  comparison: string;
  window_minutes: number;
  severity: string;
  enabled: boolean;
  updated_by: string;
  updated_at: string;
}

export default function AlertsPage() {
  const q = useQuery({
    queryKey: adminQk.alerts(),
    queryFn: () => api.request<{ alerts: AlertRow[] }>("/api/v1/admin/alerts"),
  });

  return (
    <div className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">告警规则</h1>
      {q.isLoading ? (
        <Spinner />
      ) : (
        <DataTable<AlertRow>
          columns={[
            { key: "metric", header: "指标" },
            { key: "threshold", header: "阈值" },
            { key: "comparison", header: "比较" },
            { key: "window_minutes", header: "窗口 (min)" },
            {
              key: "severity",
              header: "等级",
              render: (r) => (
                <Badge tone={r.severity === "critical" ? "danger" : "warning"}>{r.severity}</Badge>
              ),
            },
            {
              key: "enabled",
              header: "启用",
              render: (r) => (r.enabled ? <Badge tone="success">ON</Badge> : <Badge>OFF</Badge>),
            },
          ]}
          rows={q.data?.alerts ?? []}
          getRowKey={(r) => r.rule_id}
        />
      )}
    </div>
  );
}
