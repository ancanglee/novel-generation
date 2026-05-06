import { create } from "zustand";

export interface Principal {
  userId: string;
  teamId: string;
  email: string;
  globalRole: string;
  teamRole: string;
}

interface SessionState {
  principal: Principal | null;
  csrf: string | null;
  activeTeamId: string | null;
  ready: boolean;
  setPrincipal(p: Principal | null, csrf: string | null): void;
  setActiveTeam(teamId: string): void;
  markReady(): void;
  clear(): void;
}

export const useSessionStore = create<SessionState>((set) => ({
  principal: null,
  csrf: null,
  activeTeamId: null,
  ready: false,
  setPrincipal: (principal, csrf) =>
    set((s) => ({
      principal,
      csrf,
      activeTeamId: principal?.teamId ?? s.activeTeamId,
    })),
  setActiveTeam: (teamId) => set({ activeTeamId: teamId }),
  markReady: () => set({ ready: true }),
  clear: () => set({ principal: null, csrf: null, activeTeamId: null }),
}));
