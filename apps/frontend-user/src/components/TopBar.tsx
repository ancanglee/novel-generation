import { Button } from "@novelgen/ui";
import { Link, NavLink } from "react-router-dom";
import { common } from "../strings";
import { useSessionStore } from "../stores/sessionStore";
import { TeamPicker } from "./TeamPicker";

const navItems = [
  { to: "/", label: common.nav.dashboard, end: true },
  { to: "/novels", label: common.nav.novels },
  { to: "/settings", label: common.nav.settings },
];

export function TopBar() {
  const principal = useSessionStore((s) => s.principal);
  const isAdmin = principal?.globalRole === "admin";

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background/90 px-6 backdrop-blur">
      <div className="flex items-center gap-6">
        <Link to="/" className="text-base font-semibold">
          {common.appName}
        </Link>
        <nav aria-label="主导航" className="flex items-center gap-4">
          {navItems.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `text-sm transition-colors ${
                  isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
          {isAdmin ? (
            <a
              href="/admin"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Admin Console
            </a>
          ) : null}
        </nav>
      </div>
      <div className="flex items-center gap-3">
        <TeamPicker />
        <span className="hidden text-sm text-muted-foreground sm:inline">
          {principal?.email ?? ""}
        </span>
        <form action="/auth/logout" method="post">
          <Button type="submit" variant="ghost" size="sm">
            {common.nav.logout}
          </Button>
        </form>
      </div>
    </header>
  );
}
