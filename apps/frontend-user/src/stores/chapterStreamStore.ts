import { create } from "zustand";

export type ChapterPhase =
  | "idle"
  | "connecting"
  | "streaming"
  | "completed"
  | "cancelling"
  | "cancelled"
  | "failed";

interface ChapterStreamState {
  gid: string | null;
  chapterIdx: number | null;
  phase: ChapterPhase;
  buffer: string;
  lastEventId: string | null;
  firstByteAt: number | null;
  completedAt: number | null;
  error: string | null;
  reconnectCount: number;

  start(gid: string, chapterIdx: number): void;
  setConnecting(): void;
  setStreamingIfIdle(): void;
  appendBuffer(text: string): void;
  setLastEventId(id: string): void;
  markFirstByte(): void;
  markCompleted(): void;
  markFailed(msg: string): void;
  requestCancel(): void;
  markCancelled(): void;
  incrementReconnect(): number;
  reset(): void;
}

export const useChapterStreamStore = create<ChapterStreamState>((set, get) => ({
  gid: null,
  chapterIdx: null,
  phase: "idle",
  buffer: "",
  lastEventId: null,
  firstByteAt: null,
  completedAt: null,
  error: null,
  reconnectCount: 0,

  start: (gid, chapterIdx) =>
    set({
      gid,
      chapterIdx,
      phase: "connecting",
      buffer: "",
      lastEventId: null,
      firstByteAt: null,
      completedAt: null,
      error: null,
      reconnectCount: 0,
    }),

  setConnecting: () => set({ phase: "connecting" }),

  setStreamingIfIdle: () => {
    if (get().phase === "connecting") set({ phase: "streaming" });
  },

  appendBuffer: (text) => set((s) => ({ buffer: s.buffer + text })),
  setLastEventId: (id) => set({ lastEventId: id }),

  markFirstByte: () =>
    set((s) => (s.firstByteAt ? s : { firstByteAt: performance.now(), phase: "streaming" })),

  markCompleted: () =>
    set({
      phase: "completed",
      completedAt: performance.now(),
    }),

  markFailed: (msg) => set({ phase: "failed", error: msg }),

  requestCancel: () => {
    const phase = get().phase;
    if (phase === "streaming" || phase === "connecting") set({ phase: "cancelling" });
  },

  markCancelled: () => set({ phase: "cancelled" }),

  incrementReconnect: () => {
    const next = get().reconnectCount + 1;
    set({ reconnectCount: next });
    return next;
  },

  reset: () =>
    set({
      gid: null,
      chapterIdx: null,
      phase: "idle",
      buffer: "",
      lastEventId: null,
      firstByteAt: null,
      completedAt: null,
      error: null,
      reconnectCount: 0,
    }),
}));
