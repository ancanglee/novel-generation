import { create } from "zustand";

interface ConflictPanelState {
  open: boolean;
  selectedConflictId: string | null;
  busyIds: Set<string>;
  toggleOpen(): void;
  setOpen(open: boolean): void;
  setSelected(id: string | null): void;
  markBusy(id: string): void;
  clearBusy(id: string): void;
}

export const useConflictPanelStore = create<ConflictPanelState>((set) => ({
  open: true,
  selectedConflictId: null,
  busyIds: new Set<string>(),
  toggleOpen: () => set((s) => ({ open: !s.open })),
  setOpen: (open) => set({ open }),
  setSelected: (id) => set({ selectedConflictId: id }),
  markBusy: (id) =>
    set((s) => {
      const next = new Set(s.busyIds);
      next.add(id);
      return { busyIds: next };
    }),
  clearBusy: (id) =>
    set((s) => {
      const next = new Set(s.busyIds);
      next.delete(id);
      return { busyIds: next };
    }),
}));
