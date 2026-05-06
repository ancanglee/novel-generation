import { Badge, Button, Spinner } from "@novelgen/ui";
import { Link, useParams } from "react-router-dom";
import { useNovel } from "../../hooks/useNovels";

export default function NovelDetailPage() {
  const { novelId } = useParams();
  const novel = useNovel(novelId);

  if (novel.isLoading) {
    return <div className="p-8 flex gap-2 items-center"><Spinner /> 加载小说…</div>;
  }
  if (!novel.data) {
    return <div className="p-8 text-sm text-muted-foreground">未找到该小说</div>;
  }

  const n = novel.data;
  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{n.title}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <Badge tone="info">{n.source_type}</Badge>
            <span>{n.chapter_count} 章</span>
            <span>·</span>
            <span>{new Date(n.created_at).toLocaleString()}</span>
          </p>
        </div>
        <div className="flex gap-2">
          <Link to={`/novels/${novelId}/analysis`}>
            <Button>查看分析</Button>
          </Link>
        </div>
      </header>

      <section className="rounded-lg border bg-card p-4 text-sm text-muted-foreground">
        <p>在分析页查看人物关系、地图、风格雷达；或基于此小说创建新的生成任务。</p>
      </section>
    </div>
  );
}
