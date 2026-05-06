import { Toast as UiToast, type ToastVariant } from "@novelgen/ui";
import { create } from "zustand";

interface ToastEntry {
  id: string;
  variant: ToastVariant;
  title: string;
  description?: string;
  ttlMs: number;
}

interface ToastState {
  toasts: ToastEntry[];
  push(entry: Omit<ToastEntry, "id" | "ttlMs"> & { ttlMs?: number }): void;
  dismiss(id: string): void;
}

const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: (entry) => {
    const id = crypto.randomUUID();
    const ttlMs = entry.ttlMs ?? 4000;
    set((s) => ({ toasts: [...s.toasts, { ...entry, id, ttlMs }] }));
    setTimeout(() => {
      get().dismiss(id);
    }, ttlMs);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

export function toast(entry: Parameters<ToastState["push"]>[0]): void {
  useToastStore.getState().push(entry);
}

export function ToastRegion() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);
  return (
    <div className="pointer-events-none fixed right-4 top-16 z-50 flex w-80 flex-col gap-2">
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto">
          <UiToast
            variant={t.variant}
            title={t.title}
            description={t.description}
            onDismiss={() => dismiss(t.id)}
          />
        </div>
      ))}
    </div>
  );
}
