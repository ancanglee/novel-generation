import type { ReactNode } from "react";
import { cn } from "../lib/cn";

export type ToastVariant = "success" | "warning" | "error" | "info";

export interface ToastProps {
  variant?: ToastVariant;
  title: string;
  description?: string;
  children?: ReactNode;
  onDismiss?(): void;
}

const variantClasses: Record<ToastVariant, string> = {
  success: "border-emerald-500/30 bg-emerald-50 text-emerald-900",
  warning: "border-amber-500/30 bg-amber-50 text-amber-900",
  error: "border-red-500/30 bg-red-50 text-red-900",
  info: "border-sky-500/30 bg-sky-50 text-sky-900",
};

export function Toast({ variant = "info", title, description, children, onDismiss }: ToastProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn("rounded-md border px-4 py-3 shadow-sm", variantClasses[variant])}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold">{title}</p>
          {description ? <p className="mt-1 text-sm opacity-90">{description}</p> : null}
          {children}
        </div>
        {onDismiss ? (
          <button
            type="button"
            onClick={onDismiss}
            className="rounded p-1 text-sm hover:bg-black/5"
            aria-label="关闭提示"
          >
            ×
          </button>
        ) : null}
      </div>
    </div>
  );
}
