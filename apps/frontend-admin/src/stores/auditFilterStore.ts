import { create } from "zustand";

interface AuditFilterState {
  dateFrom: string | null;
  dateTo: string | null;
  teamId: string | null;
  userId: string | null;
  actionContains: string;
  cursor: string | null;
  set(patch: Partial<Omit<AuditFilterState, "set" | "reset">>): void;
  reset(): void;
}

const initial = {
  dateFrom: null,
  dateTo: null,
  teamId: null,
  userId: null,
  actionContains: "",
  cursor: null,
};

export const useAuditFilterStore = create<AuditFilterState>((set) => ({
  ...initial,
  set: (patch) => set(patch),
  reset: () => set(initial),
}));
