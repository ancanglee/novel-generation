import { Badge, Button, StreamingText } from "@novelgen/ui";
import { useParams } from "react-router-dom";
import { useChapterStreamStore } from "../../stores/chapterStreamStore";
import { chapter } from "../../strings";
import { ConflictPanelContainer } from "./ConflictPanelContainer";
import { useChapterStream } from "./useChapterStream";

const phaseTone: Record<
  ReturnType<typeof useChapterStreamStore.getState>["phase"],
  "default" | "success" | "warning" | "danger" | "info"
> = {
  idle: "default",
  connecting: "info",
  streaming: "info",
  completed: "success",
  cancelling: "warning",
  cancelled: "default",
  failed: "danger",
};

export default function ChapterPage() {
  const { gid, n } = useParams();
  const chapterIdx = n ? Number.parseInt(n, 10) : undefined;
  const stream = useChapterStreamStore();
  const { requestCancel } = useChapterStream(gid, chapterIdx);

  const isStreaming = stream.phase === "connecting" || stream.phase === "streaming";

  return (
    <div className="grid h-[calc(100vh-3.5rem)] grid-cols-[1fr_22rem]">
      <section className="flex flex-col overflow-hidden border-r">
        <header className="flex items-center justify-between border-b px-6 py-3">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-medium">{chapter.title(chapterIdx ?? 0)}</h2>
            <Badge tone={phaseTone[stream.phase]}>{chapter.phase[stream.phase]}</Badge>
            {stream.reconnectCount > 0 && isStreaming ? (
              <span className="text-xs text-muted-foreground">
                {chapter.stream.reconnecting(stream.reconnectCount)}
              </span>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={!isStreaming}
              onClick={() => {
                void requestCancel();
              }}
            >
              {chapter.actions.cancel}
            </Button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto bg-background px-6 py-6">
          <StreamingText
            text={stream.buffer}
            isStreaming={isStreaming}
            autoscroll
            className="mx-auto max-w-3xl text-base"
          />
          {stream.phase === "failed" ? (
            <p className="mx-auto mt-4 max-w-3xl rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
              {stream.error ?? chapter.stream.failed}
            </p>
          ) : null}
        </div>
      </section>

      <aside className="overflow-hidden">{gid ? <ConflictPanelContainer gid={gid} /> : null}</aside>
    </div>
  );
}
