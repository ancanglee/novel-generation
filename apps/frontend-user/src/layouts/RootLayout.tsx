import { Spinner } from "@novelgen/ui";
import { Outlet } from "react-router-dom";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { ToastRegion } from "../components/Toast";
import { TopBar } from "../components/TopBar";
import { useAuth } from "../hooks/useAuth";
import { useSessionStore } from "../stores/sessionStore";

export default function RootLayout() {
  useAuth();
  const ready = useSessionStore((s) => s.ready);
  const principal = useSessionStore((s) => s.principal);

  if (!ready) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!principal) {
    // Not signed in — BFF will 302 on next protected API call.
    return (
      <div className="mx-auto max-w-md p-8 text-center">
        <h1 className="text-lg font-semibold">欢迎使用 NovelGen</h1>
        <p className="mt-2 text-sm text-muted-foreground">请先登录</p>
        <a
          href="/auth/login"
          className="mt-6 inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
        >
          登录
        </a>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="flex min-h-full flex-col">
        <TopBar />
        <main className="flex-1">
          <Outlet />
        </main>
        <ToastRegion />
      </div>
    </ErrorBoundary>
  );
}
