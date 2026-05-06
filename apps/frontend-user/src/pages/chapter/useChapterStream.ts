import { useEffect, useRef } from "react";
import { openChapterStream } from "../../lib/sse";
import { emit } from "../../lib/telemetry";
import { useChapterStreamStore } from "../../stores/chapterStreamStore";

const MAX_RECONNECT = 5;
const CANCEL_TIMEOUT_MS = 8_000;

export function useChapterStream(gid: string | undefined, chapterIdx: number | undefined) {
  const store = useChapterStreamStore();
  const pendingRef = useRef("");
  const rafRef = useRef<number | null>(null);
  const handleRef = useRef<ReturnType<typeof openChapterStream> | null>(null);
  const clickAtRef = useRef<number | null>(null);

  useEffect(() => {
    if (!gid || !chapterIdx) return;
    store.start(gid, chapterIdx);
    clickAtRef.current = performance.now();

    const flush = (): void => {
      if (pendingRef.current) {
        store.appendBuffer(pendingRef.current);
        pendingRef.current = "";
      }
      rafRef.current = null;
    };
    const schedule = (): void => {
      if (rafRef.current != null) return;
      rafRef.current = requestAnimationFrame(flush);
    };

    let disposed = false;

    const connect = (): void => {
      if (disposed) return;
      handleRef.current = openChapterStream(gid, chapterIdx, {
        onOpen: () => useChapterStreamStore.getState().setConnecting(),
        onDelta: (eventId, text) => {
          pendingRef.current += text;
          store.setLastEventId(eventId);
          if (!useChapterStreamStore.getState().firstByteAt) {
            store.markFirstByte();
            const t0 = clickAtRef.current ?? performance.now();
            emit({
              name: "SseTtftMs",
              unit: "Milliseconds",
              value: performance.now() - t0,
              route: `/generations/${gid}/chapters/${chapterIdx}`,
            });
          }
          schedule();
        },
        onCompleted: () => {
          flush();
          store.markCompleted();
        },
        onCancelled: () => {
          flush();
          store.markCancelled();
        },
        onError: (data) => {
          flush();
          const n = store.incrementReconnect();
          if (n <= MAX_RECONNECT) {
            emit({ name: "SseReconnectCount", unit: "Count", value: 1 });
            const delay = Math.min(16_000, 1000 * 2 ** (n - 1));
            setTimeout(connect, delay);
          } else {
            store.markFailed(
              typeof data === "object" ? JSON.stringify(data) : String(data ?? "SSE_FAILED"),
            );
          }
        },
      });
    };

    connect();

    return () => {
      disposed = true;
      handleRef.current?.close();
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      handleRef.current = null;
    };
  }, [gid, chapterIdx, store]);

  /** User-triggered cancel. Fires cancel HTTP + 8s force-close fallback. */
  const requestCancel = async (): Promise<void> => {
    if (!gid || !chapterIdx) return;
    store.requestCancel();
    try {
      const res = await fetch(`/api/v1/generations/${gid}/chapters/${chapterIdx}/cancel`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": document.cookie.match(/csrf=([^;]+)/)?.[1] ?? "" },
      });
      if (!res.ok) store.markFailed(`cancel_${res.status}`);
    } catch (err) {
      /* swallow — SSE may still deliver cancelled */
    }
    setTimeout(() => {
      if (useChapterStreamStore.getState().phase === "cancelling") {
        handleRef.current?.close();
        useChapterStreamStore.getState().markCancelled();
      }
    }, CANCEL_TIMEOUT_MS);
  };

  return { requestCancel };
}
