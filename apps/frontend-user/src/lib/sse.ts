export interface SseHandlers {
  onStart?(data: unknown): void;
  onDelta(eventId: string, text: string): void;
  onCompleted?(data: unknown): void;
  onCancelled?(data: unknown): void;
  onError?(data: unknown): void;
  onOpen?(): void;
}

export interface SseHandle {
  close(): void;
  readyState(): EventSource["readyState"];
}

export function openChapterStream(
  gid: string,
  chapterIdx: number,
  handlers: SseHandlers,
): SseHandle {
  const url = `/api/v1/generations/${gid}/chapters/${chapterIdx}/stream`;
  const es = new EventSource(url, { withCredentials: true });

  es.addEventListener("open", () => handlers.onOpen?.());

  es.addEventListener("start", (evt) => {
    try {
      const d = JSON.parse((evt as MessageEvent).data ?? "null");
      handlers.onStart?.(d);
    } catch {
      handlers.onStart?.(null);
    }
  });

  es.addEventListener("delta", (evt) => {
    const me = evt as MessageEvent;
    try {
      const data = JSON.parse(me.data);
      if (typeof data?.text === "string") {
        handlers.onDelta(me.lastEventId || "", data.text);
      }
    } catch {
      /* ignore malformed frames */
    }
  });

  const terminate = (type: "completed" | "cancelled" | "error", data: unknown): void => {
    if (type === "completed") handlers.onCompleted?.(data);
    else if (type === "cancelled") handlers.onCancelled?.(data);
    else handlers.onError?.(data);
    es.close();
  };

  es.addEventListener("completed", (evt) => {
    try {
      terminate("completed", JSON.parse((evt as MessageEvent).data ?? "null"));
    } catch {
      terminate("completed", null);
    }
  });
  es.addEventListener("cancelled", (evt) => {
    try {
      terminate("cancelled", JSON.parse((evt as MessageEvent).data ?? "null"));
    } catch {
      terminate("cancelled", null);
    }
  });
  es.addEventListener("error", (evt) => {
    try {
      terminate("error", JSON.parse((evt as MessageEvent).data ?? "null"));
    } catch {
      terminate("error", null);
    }
  });

  return {
    close: () => es.close(),
    readyState: () => es.readyState,
  };
}
