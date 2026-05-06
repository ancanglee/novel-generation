import type { ReactNode } from "react";
import { cn } from "@novelgen/ui";

export interface Column<T> {
  key: keyof T | string;
  header: string;
  render?(row: T): ReactNode;
  width?: string;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  empty?: string;
  getRowKey(row: T): string;
  onRowClick?(row: T): void;
  selectedKey?: string | null;
}

export function DataTable<T>({
  columns,
  rows,
  empty = "暂无数据",
  getRowKey,
  onRowClick,
  selectedKey,
}: DataTableProps<T>) {
  return (
    <div className="overflow-x-auto rounded-lg border bg-card">
      <table className="w-full text-sm">
        <thead className="border-b bg-muted/30">
          <tr>
            {columns.map((c) => (
              <th
                key={String(c.key)}
                style={c.width ? { width: c.width } : undefined}
                className="px-4 py-2 text-left font-medium"
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td className="px-4 py-6 text-muted-foreground" colSpan={columns.length}>
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row) => {
              const key = getRowKey(row);
              return (
                <tr
                  key={key}
                  onClick={() => onRowClick?.(row)}
                  className={cn(
                    "border-b last:border-b-0 transition-colors",
                    onRowClick && "cursor-pointer hover:bg-accent/40",
                    selectedKey === key && "bg-accent/60",
                  )}
                >
                  {columns.map((c) => (
                    <td key={String(c.key)} className="px-4 py-2 align-top">
                      {c.render ? c.render(row) : ((row as unknown as Record<string, ReactNode>)[String(c.key)] ?? "")}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
