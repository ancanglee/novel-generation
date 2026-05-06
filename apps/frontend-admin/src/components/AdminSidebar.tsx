import { NavLink } from "react-router-dom";
import { admin } from "../strings/admin";

const navItems = [
  { to: "/admin", label: admin.nav.dashboard, end: true },
  { to: "/admin/users", label: admin.nav.users },
  { to: "/admin/teams", label: admin.nav.teams },
  { to: "/admin/model-configs", label: admin.nav.modelConfigs },
  { to: "/admin/schemas", label: admin.nav.schemas },
  { to: "/admin/templates", label: admin.nav.templates },
  { to: "/admin/monitoring", label: admin.nav.monitoring },
  { to: "/admin/audit", label: admin.nav.audit },
  { to: "/admin/alerts", label: admin.nav.alerts },
  { to: "/admin/concurrency", label: admin.nav.concurrency },
];

export function AdminSidebar() {
  return (
    <nav aria-label="管理后台导航" className="w-52 shrink-0 border-r">
      <ul className="flex flex-col py-4">
        {navItems.map((n) => (
          <li key={n.to}>
            <NavLink
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `block px-4 py-2 text-sm transition-colors ${
                  isActive ? "bg-accent font-medium" : "text-muted-foreground hover:bg-accent/40"
                }`
              }
            >
              {n.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
