import { Badge, Button, Spinner } from "@novelgen/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DataTable } from "../../components/DataTable";
import { type AdminUserRow, useUsersQuery } from "../../hooks/useUsersQuery";
import { adminQk } from "../../lib/adminQueryKeys";
import { api } from "../../lib/api";

export default function UsersPage() {
  const [confirm, setConfirm] = useState<null | { user: AdminUserRow; kind: "disable" | "reset" }>(
    null,
  );
  const qc = useQueryClient();
  const users = useUsersQuery();

  const disableMut = useMutation({
    mutationFn: (userId: string) =>
      api.request(`/api/v1/admin/users/${userId}/disable`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminQk.users(50) }),
  });
  const resetMut = useMutation({
    mutationFn: (userId: string) =>
      api.request(`/api/v1/admin/users/${userId}/reset-password`, { method: "POST" }),
  });

  const doConfirm = () => {
    if (!confirm) return;
    if (confirm.kind === "disable") disableMut.mutate(confirm.user.user_id);
    else resetMut.mutate(confirm.user.user_id);
    setConfirm(null);
  };

  return (
    <div className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">用户管理</h1>
      {users.isLoading ? (
        <Spinner />
      ) : (
        <DataTable<AdminUserRow>
          columns={[
            { key: "email", header: "邮箱" },
            { key: "display_name", header: "显示名" },
            { key: "team_id", header: "Team", render: (r) => r.team_id.slice(0, 8) },
            {
              key: "global_role",
              header: "角色",
              render: (r) => (
                <Badge tone={r.global_role === "admin" ? "success" : "default"}>
                  {r.global_role}
                </Badge>
              ),
            },
            {
              key: "status",
              header: "状态",
              render: (r) => (
                <Badge tone={r.status === "active" ? "success" : "danger"}>{r.status}</Badge>
              ),
            },
            {
              key: "actions",
              header: "操作",
              render: (r) => (
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfirm({ user: r, kind: "reset" });
                    }}
                  >
                    重置密码
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfirm({ user: r, kind: "disable" });
                    }}
                  >
                    禁用
                  </Button>
                </div>
              ),
            },
          ]}
          rows={users.data?.users ?? []}
          getRowKey={(r) => r.user_id}
        />
      )}
      <ConfirmDialog
        open={!!confirm}
        title={confirm?.kind === "disable" ? "禁用用户" : "重置密码"}
        description={`对 ${confirm?.user.email ?? ""} 执行此操作？`}
        dangerous={confirm?.kind === "disable"}
        loading={disableMut.isPending || resetMut.isPending}
        onConfirm={doConfirm}
        onCancel={() => setConfirm(null)}
      />
    </div>
  );
}
