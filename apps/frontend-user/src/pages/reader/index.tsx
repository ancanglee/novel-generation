import { ChapterReader, type ReaderTheme, Spinner } from "@novelgen/ui";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../lib/api";

interface ChapterListItem {
  chapter_idx: number;
  title: string;
}
interface ChapterContentDto {
  chapter_idx: number;
  title: string;
  markdown: string;
}

const STORAGE_KEY = (gid: string) => `reader:${gid}:prefs`;

export default function ReaderPage() {
  const { gid } = useParams();
  const [theme, setTheme] = useState<ReaderTheme>("light");
  const [fontSize, setFontSize] = useState(16);
  const [current, setCurrent] = useState(1);

  useEffect(() => {
    if (!gid) return;
    const raw = localStorage.getItem(STORAGE_KEY(gid));
    if (!raw) return;
    try {
      const p = JSON.parse(raw);
      if (p.theme) setTheme(p.theme);
      if (typeof p.fontSize === "number") setFontSize(p.fontSize);
      if (typeof p.current === "number") setCurrent(p.current);
    } catch {
      /* noop */
    }
  }, [gid]);

  useEffect(() => {
    if (!gid) return;
    localStorage.setItem(STORAGE_KEY(gid), JSON.stringify({ theme, fontSize, current }));
  }, [gid, theme, fontSize, current]);

  const toc = useQuery({
    enabled: Boolean(gid),
    queryKey: ["reader", gid, "toc"] as const,
    queryFn: () =>
      api.request<{ chapters: ChapterListItem[] }>(`/api/v1/generations/${gid}/chapters`),
  });
  const content = useQuery({
    enabled: Boolean(gid) && Boolean(current),
    queryKey: ["reader", gid, "ch", current] as const,
    queryFn: () =>
      api.request<ChapterContentDto>(
        `/api/v1/generations/${gid}/chapters/${current}?format=markdown`,
      ),
  });

  return (
    <div className="grid h-[calc(100vh-3.5rem)] grid-cols-[16rem_1fr]">
      <aside className="overflow-y-auto border-r p-3">
        <div className="mb-3 flex flex-col gap-2">
          <label className="text-xs text-muted-foreground">主题</label>
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value as ReaderTheme)}
            className="rounded border px-2 py-1 text-sm"
          >
            <option value="light">浅色</option>
            <option value="dark">深色</option>
            <option value="sepia">护眼</option>
          </select>
          <label className="mt-2 text-xs text-muted-foreground">字号</label>
          <input
            type="range"
            min={14}
            max={22}
            value={fontSize}
            onChange={(e) => setFontSize(Number.parseInt(e.target.value, 10))}
          />
        </div>
        <ol className="space-y-1 text-sm">
          {toc.data?.chapters?.map((c) => (
            <li key={c.chapter_idx}>
              <button
                type="button"
                onClick={() => setCurrent(c.chapter_idx)}
                className={`w-full rounded px-2 py-1 text-left hover:bg-accent ${
                  current === c.chapter_idx ? "bg-accent" : ""
                }`}
              >
                {c.chapter_idx}. {c.title}
              </button>
            </li>
          ))}
        </ol>
      </aside>
      <main className="overflow-y-auto">
        {content.isLoading ? (
          <div className="flex h-full items-center justify-center">
            <Spinner />
          </div>
        ) : content.data ? (
          <ChapterReader markdown={content.data.markdown} theme={theme} fontSize={fontSize} />
        ) : null}
      </main>
    </div>
  );
}
