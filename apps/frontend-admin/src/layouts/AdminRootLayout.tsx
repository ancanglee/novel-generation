import { Spinner } from "@novelgen/ui";
import { Outlet } from "react-router-dom";
import { AdminSidebar } from "../components/AdminSidebar";
import { AdminTopBar } from "../components/AdminTopBar";
import { useAdminAuth } from "../hooks/useAdminAuth";
import { useAdminSessionStore } from "../stores/adminSessionStore";
import { admin } from "../strings/admin";

export default function AdminRootLayout() {
  useAdminAuth();
  const ready = useAdminSessionStore((s) => s.ready);
  const isAdmin = useAdminSessionStore((s) => s.isAdmin());

  if (!ready) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="mx-auto max-w-md p-12 text-center">
        <h1 className="text-xl font-semibold">{admin.errors.forbidden}</h1>
        <p className="mt-2 text-sm text-muted-foreground">请使用管理员账户登录后访问</p>
        <a
          href="/auth/login"
          className="mt-6 inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm text-primary-foreground"
        >
          登录
        </a>
      </div>
    );
  }

  return (
    <div className="flex min-h-full flex-col">
      <AdminTopBar />
      <div className="flex min-h-[calc(100vh-3.5rem)]">
        <AdminSidebar />
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
