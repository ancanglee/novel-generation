import { Button, Spinner } from "@novelgen/ui";
import { Link } from "react-router-dom";
import { useNovels } from "../../hooks/useNovels";
import { common } from "../../strings";
import IngestForm from "./IngestForm";

export default function NovelsPage() {
  const novels = useNovels();

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{common.nav.novels}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            上传、搜索公版书或抓取 URL 进行采集
          </p>
        </div>
      </header>

      <IngestForm />

      <section>
        <h2 className="mb-3 text-lg font-medium">已入库小说</h2>
        <div className="rounded-lg border bg-card">
          {novels.isLoading ? (
            <div className="flex items-center gap-2 p-4"><Spinner /> <span className="text-sm">加载中…</span></div>
          ) : novels.data?.items?.length ? (
            <ul className="divide-y">
              {novels.data.items.map((n) => (
                <li key={n.novel_id} className="flex items-center justify-between px-4 py-3">
                  <div>
                    <Link to={`/novels/${n.novel_id}`} className="font-medium hover:underline">
                      {n.title}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      {n.chapter_count} 章 · {n.source_type} · {new Date(n.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Link to={`/novels/${n.novel_id}`}>
                      <Button size="sm" variant="secondary">详情</Button>
                    </Link>
                    <Link to={`/novels/${n.novel_id}/analysis`}>
                      <Button size="sm">查看分析</Button>
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="p-4 text-sm text-muted-foreground">暂无小说，先在上方采集一本</p>
          )}
        </div>
      </section>
    </div>
  );
}
