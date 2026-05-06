import { Badge, Button } from "@novelgen/ui";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { useSessionStore } from "../../stores/sessionStore";

interface TeamMembersResponse {
  team_id: string;
  members: Array<{
    user_id: string;
    email: string;
    display_name: string;
    team_role: string;
  }>;
}

export default function SettingsPage() {
  const principal = useSessionStore((s) => s.principal);
  const members = useQuery({
    queryKey: ["teams", "current", "members"] as const,
    queryFn: () =>
      api.request<TeamMembersResponse>("/api/v1/teams/current/members"),
  });

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <section>
        <h1 className="text-2xl font-semibold">设置</h1>
      </section>
      <section className="rounded-lg border bg-card p-4">
        <h2 className="text-base font-medium">个人资料</h2>
        <dl className="mt-3 grid grid-cols-[6rem_1fr] gap-x-4 gap-y-2 text-sm">
          <dt className="text-muted-foreground">邮箱</dt>
          <dd>{principal?.email ?? "—"}</dd>
          <dt className="text-muted-foreground">用户角色</dt>
          <dd><Badge>{principal?.globalRole ?? "—"}</Badge></dd>
          <dt className="text-muted-foreground">Team 角色</dt>
          <dd><Badge tone="info">{principal?.teamRole ?? "—"}</Badge></dd>
        </dl>
      </section>
      <section className="rounded-lg border bg-card p-4">
        <h2 className="text-base font-medium">团队成员</h2>
        <div className="mt-3">
          {members.data?.members?.length ? (
            <ul className="divide-y text-sm">
              {members.data.members.map((m) => (
                <li key={m.user_id} className="flex items-center justify-between py-2">
                  <div>
                    <p className="font-medium">{m.display_name || m.email}</p>
                    <p className="text-xs text-muted-foreground">{m.email}</p>
                  </div>
                  <Badge tone={m.team_role === "owner" ? "success" : "default"}>
                    {m.team_role}
                  </Badge>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">加载中…</p>
          )}
        </div>
        {principal?.teamRole === "owner" ? (
          <div className="mt-4">
            <Button size="sm" variant="secondary">邀请成员</Button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
