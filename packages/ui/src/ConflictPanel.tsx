import type { ConflictItem } from "@novelgen/types";
import { ConflictType } from "@novelgen/types";
import { AlertTriangle, ArrowRightCircle, Check } from "lucide-react";
import { cn } from "./lib/cn";
import { Badge } from "./primitives/Badge";
import { Button } from "./primitives/Button";

const TYPE_LABELS: Record<ConflictType, { label: string; tone: "warning" | "danger" | "info" }> = {
  [ConflictType.CharacterState]: { label: "人物状态", tone: "warning" },
  [ConflictType.PlotHole]: { label: "情节漏洞", tone: "danger" },
  [ConflictType.Timeline]: { label: "时间线", tone: "warning" },
  [ConflictType.Location]: { label: "地理位置", tone: "info" },
  [ConflictType.Relation]: { label: "人物关系", tone: "warning" },
  [ConflictType.Worldbuilding]: { label: "世界观", tone: "danger" },
};

export interface ConflictPanelProps {
  conflicts: ConflictItem[];
  selectedId: string | null;
  onSelect(conflictId: string | null): void;
  onIgnore(conflictId: string): void | Promise<void>;
  onRewrite(conflictId: string): void | Promise<void>;
  busyIds?: Set<string>;
}

export function ConflictPanel({
  conflicts,
  selectedId,
  onSelect,
  onIgnore,
  onRewrite,
  busyIds,
}: ConflictPanelProps) {
  if (conflicts.length === 0) {
    return (
      <aside className="flex flex-col items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
        <Check className="size-5 text-emerald-500" aria-hidden />
        <p>暂无一致性冲突</p>
      </aside>
    );
  }
  return (
    <aside className="flex h-full flex-col">
      <header className="border-b px-4 py-3">
        <h3 className="text-sm font-semibold">一致性冲突（{conflicts.length}）</h3>
      </header>
      <ul className="flex-1 divide-y overflow-y-auto">
        {conflicts.map((ci) => {
          const type = TYPE_LABELS[ci.type];
          const busy = busyIds?.has(ci.conflict_id);
          return (
            <li
              key={ci.conflict_id}
              className={cn(
                "cursor-pointer px-4 py-3 transition-colors hover:bg-accent/40",
                selectedId === ci.conflict_id && "bg-accent/60",
              )}
              onClick={() => onSelect(ci.conflict_id)}
            >
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 size-4 text-amber-500" aria-hidden />
                <div className="flex-1">
                  <div className="flex items-center gap-2 text-xs">
                    <Badge tone={type.tone}>{type.label}</Badge>
                    <span className="text-muted-foreground">
                      第 {ci.chapter_refs.join("、")} 章
                    </span>
                    {ci.frozen ? <Badge tone="danger">已冻结</Badge> : null}
                  </div>
                  <p className="mt-2 line-clamp-3 text-sm">{ci.summary}</p>
                  <div className="mt-3 flex gap-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={busy || ci.frozen}
                      onClick={(e) => {
                        e.stopPropagation();
                        onIgnore(ci.conflict_id);
                      }}
                    >
                      忽略
                    </Button>
                    <Button
                      size="sm"
                      variant="primary"
                      leftIcon={<ArrowRightCircle className="size-4" />}
                      disabled={busy || ci.frozen}
                      title={ci.frozen ? "已尝试 3 次未能解决，请手动编辑" : undefined}
                      onClick={(e) => {
                        e.stopPropagation();
                        onRewrite(ci.conflict_id);
                      }}
                    >
                      重写
                    </Button>
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
