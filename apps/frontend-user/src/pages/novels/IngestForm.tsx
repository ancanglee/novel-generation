import { Button } from "@novelgen/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "../../components/Toast";
import { api } from "../../lib/api";
import { qk } from "../../lib/queryKeys";

interface IngestJobRef {
  job_id: string;
}

type Mode = "upload" | "search" | "url";

export default function IngestForm() {
  const [mode, setMode] = useState<Mode>("upload");
  const qc = useQueryClient();

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/v1/novels/upload", {
        method: "POST",
        credentials: "include",
        body: form,
        headers: { "X-CSRF-Token": document.cookie.match(/csrf=([^;]+)/)?.[1] ?? "" },
      });
      if (!res.ok) throw new Error(`upload_failed_${res.status}`);
      return (await res.json()) as IngestJobRef;
    },
    onSuccess: () => {
      toast({ variant: "success", title: "上传已入队" });
      qc.invalidateQueries({ queryKey: qk.novels() });
    },
    onError: () => toast({ variant: "error", title: "上传失败" }),
  });

  const searchMutation = useMutation({
    mutationFn: (keyword: string) =>
      api.request<IngestJobRef>("/api/v1/novels/search-and-download", {
        method: "POST",
        body: { keyword },
      }),
    onSuccess: () => {
      toast({ variant: "success", title: "搜索任务已入队" });
      qc.invalidateQueries({ queryKey: qk.novels() });
    },
  });

  const urlMutation = useMutation({
    mutationFn: (url: string) =>
      api.request<IngestJobRef>("/api/v1/novels/crawl", {
        method: "POST",
        body: { url },
      }),
    onSuccess: () => {
      toast({ variant: "success", title: "抓取任务已入队" });
      qc.invalidateQueries({ queryKey: qk.novels() });
    },
  });

  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="mb-3 flex gap-2">
        <TabButton active={mode === "upload"} onClick={() => setMode("upload")}>本地上传</TabButton>
        <TabButton active={mode === "search"} onClick={() => setMode("search")}>公版书搜索</TabButton>
        <TabButton active={mode === "url"} onClick={() => setMode("url")}>URL 抓取</TabButton>
      </div>

      {mode === "upload" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const input = (e.currentTarget.elements.namedItem("file") as HTMLInputElement);
            const f = input.files?.[0];
            if (f) uploadMutation.mutate(f);
          }}
          className="flex flex-wrap items-center gap-2"
        >
          <input
            name="file"
            type="file"
            accept=".txt,.md,.epub,.pdf,.docx"
            className="text-sm"
            required
          />
          <Button type="submit" loading={uploadMutation.isPending}>
            开始上传
          </Button>
        </form>
      ) : null}

      {mode === "search" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const input = (e.currentTarget.elements.namedItem("keyword") as HTMLInputElement);
            if (input.value.trim().length >= 2) searchMutation.mutate(input.value.trim());
          }}
          className="flex flex-wrap items-center gap-2"
        >
          <input
            name="keyword"
            placeholder="书名 / 作者关键词（≥2 字）"
            className="h-10 flex-1 rounded-md border px-3 text-sm"
            minLength={2}
            required
          />
          <Button type="submit" loading={searchMutation.isPending}>搜索并下载</Button>
        </form>
      ) : null}

      {mode === "url" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const input = (e.currentTarget.elements.namedItem("url") as HTMLInputElement);
            if (input.validity.valid) urlMutation.mutate(input.value);
          }}
          className="flex flex-wrap items-center gap-2"
        >
          <input
            name="url"
            type="url"
            placeholder="https://…"
            className="h-10 flex-1 rounded-md border px-3 text-sm"
            required
          />
          <Button type="submit" loading={urlMutation.isPending}>抓取</Button>
        </form>
      ) : null}
    </section>
  );
}

function TabButton({ active, children, ...rest }: React.ComponentProps<"button"> & { active: boolean }) {
  return (
    <button
      type="button"
      {...rest}
      className={`rounded-md px-3 py-1 text-sm ${
        active ? "bg-primary text-primary-foreground" : "border hover:bg-accent"
      }`}
    >
      {children}
    </button>
  );
}
