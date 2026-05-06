import { create } from "zustand";

export interface AdminPrincipal {
  userId: string;
  teamId: string;
  email: string;
  globalRole: string;
  teamRole: string;
}

interface AdminSessionState {
  principal: AdminPrincipal | null;
  ready: boolean;
  setPrincipal(p: AdminPrincipal | null): void;
  markReady(): void;
  isAdmin(): boolean;
  clear(): void;
}

export const useAdminSessionStore = create<AdminSessionState>((set, get) => ({
  principal: null,
  ready: false,
  setPrincipal: (principal) => set({ principal }),
  markReady: () => set({ ready: true }),
  isAdmin: () => get().principal?.globalRole === "admin",
  clear: () => set({ principal: null }),
}));
