import { Button } from "@novelgen/ui";
import { Link } from "react-router-dom";
import { useAdminSessionStore } from "../stores/adminSessionStore";
import { admin } from "../strings/admin";

export function AdminTopBar() {
  const p = useAdminSessionStore((s) => s.principal);
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background/90 px-6 backdrop-blur">
      <Link to="/admin" className="text-base font-semibold">
        {admin.appName}
      </Link>
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">{p?.email ?? ""}</span>
        <form action="/auth/logout" method="post">
          <Button type="submit" size="sm" variant="ghost">
            {admin.nav.logout}
          </Button>
        </form>
      </div>
    </header>
  );
}
