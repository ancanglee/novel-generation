import { Suspense, lazy } from "react";
import { cn } from "./lib/cn";
import { Spinner } from "./primitives/Spinner";

const Markdown = lazy(async () => {
  const mod = await import("react-markdown");
  return { default: mod.default };
});

export type ReaderTheme = "light" | "dark" | "sepia";

export interface ChapterReaderProps {
  markdown: string;
  theme?: ReaderTheme;
  fontSize?: number;
  lineHeight?: number;
  className?: string;
}

const themeClasses: Record<ReaderTheme, string> = {
  light: "bg-white text-gray-900",
  dark: "bg-slate-900 text-slate-100",
  sepia: "bg-[#f4ecd8] text-[#433422]",
};

export function ChapterReader({
  markdown,
  theme = "light",
  fontSize = 16,
  lineHeight = 1.8,
  className,
}: ChapterReaderProps) {
  return (
    <article
      className={cn(
        "prose mx-auto max-w-3xl rounded-lg px-6 py-8 leading-relaxed",
        themeClasses[theme],
        className,
      )}
      style={{ fontSize, lineHeight }}
    >
      <Suspense fallback={<Spinner />}>
        <Markdown>{markdown}</Markdown>
      </Suspense>
    </article>
  );
}
