import { Link } from "react-router-dom";
import { admin } from "../strings/admin";

export default function AdminDashboard() {
  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold">{admin.nav.dashboard}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          管理平台配置、监控运行状态与审计操作记录
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card to="/admin/model-configs" title={admin.nav.modelConfigs} desc="按 9 个任务阶段配置 Claude 模型" />
        <Card to="/admin/monitoring" title={admin.nav.monitoring} desc="聚合 CloudWatch 指标总览" />
        <Card to="/admin/audit" title={admin.nav.audit} desc="查询和查看管理操作审计记录" />
        <Card to="/admin/users" title={admin.nav.users} desc="用户启停、重置密码、角色管理" />
        <Card to="/admin/teams" title={admin.nav.teams} desc="团队启停与改名" />
        <Card to="/admin/alerts" title={admin.nav.alerts} desc="告警规则阈值与开关" />
      </div>
    </div>
  );
}

function Card({ to, title, desc }: { to: string; title: string; desc: string }) {
  return (
    <Link to={to} className="block rounded-lg border bg-card p-4 transition-colors hover:bg-accent/40">
      <p className="text-base font-medium">{title}</p>
      <p className="mt-2 text-sm text-muted-foreground">{desc}</p>
    </Link>
  );
}
