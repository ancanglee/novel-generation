import { create } from "zustand";

export type ModalKind = "create_generation" | "edit_outline" | "rewrite_confirm" | "export" | null;

interface ModalState {
  kind: ModalKind;
  payload: Record<string, unknown>;
  open(kind: Exclude<ModalKind, null>, payload?: Record<string, unknown>): void;
  close(): void;
}

export const useModalStore = create<ModalState>((set) => ({
  kind: null,
  payload: {},
  open: (kind, payload = {}) => set({ kind, payload }),
  close: () => set({ kind: null, payload: {} }),
}));
