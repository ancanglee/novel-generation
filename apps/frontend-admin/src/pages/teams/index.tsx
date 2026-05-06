import { Badge, Spinner } from "@novelgen/ui";
import { useQuery } from "@tanstack/react-query";
import { DataTable } from "../../components/DataTable";
import { api } from "../../lib/api";
import { adminQk } from "../../lib/adminQueryKeys";

interface TeamRow {
  team_id: string;
  name: string;
  status: string;
  member_count?: number;
  novels_count?: number;
  generations_count?: number;
  created_at?: string;
}

export default function TeamsPage() {
  const q = useQuery({
    queryKey: adminQk.teams(),
    queryFn: () =>
      api.request<{ teams: TeamRow[]; count: number }>("/api/v1/admin/teams"),
  });

  return (
    <div className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">团队管理</h1>
      {q.isLoading ? <Spinner /> : (
        <DataTable<TeamRow>
          columns={[
            { key: "name", header: "名称" },
            { key: "team_id", header: "Team ID", render: (r) => <code className="text-xs">{r.team_id.slice(0, 12)}</code> },
            { key: "member_count", header: "成员" },
            { key: "novels_count", header: "小说" },
            { key: "generations_count", header: "生成任务" },
            { key: "status", header: "状态", render: (r) => <Badge tone={r.status === "active" ? "success" : "danger"}>{r.status}</Badge> },
          ]}
          rows={q.data?.teams ?? []}
          getRowKey={(r) => r.team_id}
        />
      )}
    </div>
  );
}
