import { Badge, Button, Spinner } from "@novelgen/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { DataTable } from "../../components/DataTable";
import { adminQk } from "../../lib/adminQueryKeys";
import { api } from "../../lib/api";
import { useAuditFilterStore } from "../../stores/auditFilterStore";
import { EventDetailDrawer } from "./EventDetailDrawer";

interface AuditRow {
  event_id: string;
  timestamp: string;
  actor_email: string;
  action: string;
  resource_type: string;
  resource_id: string;
  team_id: string;
  client_ip?: string;
  details: Record<string, unknown>;
}

export default function AuditPage() {
  const filter = useAuditFilterStore();
  const key = JSON.stringify({
    date_from: filter.dateFrom,
    date_to: filter.dateTo,
    team_id: filter.teamId,
    user_id: filter.userId,
    action_contains: filter.actionContains,
    cursor: filter.cursor,
  });
  const q = useQuery({
    queryKey: adminQk.audit(key),
    queryFn: () =>
      api.request<{ items: AuditRow[]; next_cursor: string | null }>("/api/v1/admin/audit", {
        query: {
          date_from: filter.dateFrom ?? undefined,
          date_to: filter.dateTo ?? undefined,
          team_id: filter.teamId ?? undefined,
          user_id: filter.userId ?? undefined,
          action_contains: filter.actionContains || undefined,
          cursor: filter.cursor ?? undefined,
          limit: 50,
        },
      }),
  });
  const [selected, setSelected] = useState<AuditRow | null>(null);

  return (
    <div className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">审计日志</h1>
      <div className="grid gap-2 sm:grid-cols-[1fr_1fr_1fr_auto]">
        <input
          type="datetime-local"
          value={filter.dateFrom ?? ""}
          onChange={(e) => filter.set({ dateFrom: e.target.value || null, cursor: null })}
          className="h-9 rounded-md border px-2 text-sm"
        />
        <input
          type="datetime-local"
          value={filter.dateTo ?? ""}
          onChange={(e) => filter.set({ dateTo: e.target.value || null, cursor: null })}
          className="h-9 rounded-md border px-2 text-sm"
        />
        <input
          placeholder="action 关键字"
          value={filter.actionContains}
          onChange={(e) => filter.set({ actionContains: e.target.value, cursor: null })}
          className="h-9 rounded-md border px-2 text-sm"
        />
        <Button size="sm" variant="ghost" onClick={filter.reset}>
          重置
        </Button>
      </div>
      {q.isLoading ? (
        <Spinner />
      ) : (
        <DataTable<AuditRow>
          columns={[
            {
              key: "timestamp",
              header: "时间",
              render: (r) => new Date(r.timestamp).toLocaleString(),
            },
            { key: "actor_email", header: "操作者" },
            { key: "action", header: "动作", render: (r) => <Badge tone="info">{r.action}</Badge> },
            { key: "resource_type", header: "资源类型" },
            { key: "resource_id", header: "资源 ID" },
          ]}
          rows={q.data?.items ?? []}
          getRowKey={(r) => r.event_id}
          onRowClick={(r) => setSelected(r)}
          selectedKey={selected?.event_id ?? null}
        />
      )}
      {q.data?.next_cursor ? (
        <div className="flex justify-center">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => filter.set({ cursor: q.data.next_cursor })}
          >
            加载下一页
          </Button>
        </div>
      ) : null}
      {selected ? <EventDetailDrawer event={selected} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}
