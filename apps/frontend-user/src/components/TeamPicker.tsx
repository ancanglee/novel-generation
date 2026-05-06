import { useQueryClient } from "@tanstack/react-query";
import { useSessionStore } from "../stores/sessionStore";

/**
 * Minimal Team picker: reads principal.teamId (single-team V1).
 * When the user belongs to multiple teams the dropdown expands —
 * switching calls `queryClient.clear()` + `queryClient.cancelQueries()`
 * to prevent cross-team data leaks (NFR-U6 R2).
 */
export function TeamPicker() {
  const principal = useSessionStore((s) => s.principal);
  const activeTeamId = useSessionStore((s) => s.activeTeamId);
  const setActiveTeam = useSessionStore((s) => s.setActiveTeam);
  const queryClient = useQueryClient();

  if (!principal) return null;

  // V1: only one team per principal. Render as a non-interactive chip.
  return (
    <button
      type="button"
      className="rounded-md border px-2 py-1 text-xs text-muted-foreground"
      onClick={() => {
        // Single-team — no-op, but illustrates the clear-cache pattern.
        void queryClient.cancelQueries();
        queryClient.clear();
        setActiveTeam(principal.teamId);
      }}
      title="当前团队"
    >
      Team {activeTeamId?.slice(0, 8) ?? principal.teamId.slice(0, 8)}
    </button>
  );
}
