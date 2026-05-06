import { ApiConflictFrozenError } from "@novelgen/api-client";
import type { ConflictItem } from "@novelgen/types";
import { ConflictPanel } from "@novelgen/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "../../components/Toast";
import { api } from "../../lib/api";
import { qk } from "../../lib/queryKeys";
import { useConflictPanelStore } from "../../stores/conflictPanelStore";
import { conflict } from "../../strings";

interface ConsistencyListItem {
  scan_to: number;
  report: { conflicts: ConflictItem[] };
}
interface ConsistencyListResponse {
  reports: ConsistencyListItem[];
}

export function ConflictPanelContainer({ gid }: { gid: string }) {
  const qc = useQueryClient();
  const selected = useConflictPanelStore((s) => s.selectedConflictId);
  const setSelected = useConflictPanelStore((s) => s.setSelected);
  const busyIds = useConflictPanelStore((s) => s.busyIds);
  const markBusy = useConflictPanelStore((s) => s.markBusy);
  const clearBusy = useConflictPanelStore((s) => s.clearBusy);

  const reports = useQuery({
    queryKey: qk.consistency(gid, 0),
    queryFn: () =>
      api.request<ConsistencyListResponse>(`/api/v1/generations/${gid}/consistency-reports`, {
        query: { since_chapter: 0, limit: 50 },
      }),
  });

  const flatConflicts: ConflictItem[] =
    reports.data?.reports?.flatMap((r) => r.report?.conflicts ?? []) ?? [];

  const ignoreMut = useMutation({
    mutationFn: (conflictId: string) =>
      api.request(`/api/v1/conflicts/${conflictId}/ignore`, { method: "POST" }),
    onMutate: (id) => markBusy(id),
    onSettled: (_d, _e, id) => clearBusy(id),
    onSuccess: () => {
      toast({ variant: "success", title: "已忽略" });
      qc.invalidateQueries({ queryKey: qk.consistency(gid, 0) });
    },
    onError: () => toast({ variant: "error", title: conflict.errors.rewriteFailed }),
  });

  const rewriteMut = useMutation({
    mutationFn: (conflictId: string) =>
      api.request(`/api/v1/conflicts/${conflictId}/rewrite`, { method: "POST" }),
    onMutate: (id) => markBusy(id),
    onSettled: (_d, _e, id) => clearBusy(id),
    onSuccess: () => {
      toast({ variant: "success", title: "已触发重写" });
      qc.invalidateQueries({ queryKey: qk.consistency(gid, 0) });
    },
    onError: (err) => {
      if (err instanceof ApiConflictFrozenError) {
        toast({ variant: "warning", title: conflict.errors.frozen });
      } else {
        toast({ variant: "error", title: conflict.errors.rewriteFailed });
      }
      qc.invalidateQueries({ queryKey: qk.consistency(gid, 0) });
    },
  });

  return (
    <ConflictPanel
      conflicts={flatConflicts}
      selectedId={selected}
      onSelect={setSelected}
      onIgnore={(id) => ignoreMut.mutate(id)}
      onRewrite={(id) => rewriteMut.mutate(id)}
      busyIds={busyIds}
    />
  );
}
