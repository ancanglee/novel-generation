import { Button } from "@novelgen/ui";
import { useNavigate, useRouteError } from "react-router-dom";
import { common } from "../strings";

export default function ErrorFallback() {
  const err = useRouteError() as { statusText?: string; message?: string };
  const navigate = useNavigate();
  return (
    <div className="mx-auto max-w-xl p-12 text-center">
      <h1 className="text-xl font-semibold">出了点问题</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        {err?.statusText ?? err?.message ?? common.errors.tryAgain}
      </p>
      <div className="mt-6 flex justify-center gap-2">
        <Button onClick={() => navigate("/")}>返回首页</Button>
        <Button variant="secondary" onClick={() => location.reload()}>
          {common.actions.retry}
        </Button>
      </div>
    </div>
  );
}
