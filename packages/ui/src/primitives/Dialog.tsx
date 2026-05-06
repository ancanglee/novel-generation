import { type ReactNode, useEffect, useRef } from "react";
import { cn } from "../lib/cn";

export interface DialogProps {
  open: boolean;
  onOpenChange(open: boolean): void;
  title?: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}

/**
 * Minimal accessible dialog backed by <dialog>. Trap focus via native modal behavior.
 */
export function Dialog({ open, onOpenChange, title, description, children, footer }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={cn(
        "rounded-lg border bg-background p-6 shadow-lg backdrop:bg-black/50",
        "w-[min(90vw,32rem)]",
      )}
      onClose={() => onOpenChange(false)}
      onClick={(e) => {
        if (e.target === ref.current) onOpenChange(false);
      }}
    >
      {title ? <h2 className="mb-2 text-lg font-semibold">{title}</h2> : null}
      {description ? (
        <p className="mb-4 text-sm text-muted-foreground">{description}</p>
      ) : null}
      <div>{children}</div>
      {footer ? <div className="mt-6 flex justify-end gap-2">{footer}</div> : null}
    </dialog>
  );
}
