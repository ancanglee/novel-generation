import { useEffect, useRef } from "react";
import { cn } from "./lib/cn";

export interface StreamingTextProps {
  text: string;
  isStreaming: boolean;
  autoscroll?: boolean;
  className?: string;
  cursorClassName?: string;
}

/**
 * Displays a growing text buffer with a blinking cursor at the end while `isStreaming`.
 * Caller is responsible for appending deltas to `text` (rAF-coalesced upstream).
 */
export function StreamingText({
  text,
  isStreaming,
  autoscroll = true,
  className,
  cursorClassName,
}: StreamingTextProps) {
  const endRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (autoscroll && isStreaming && endRef.current) {
      endRef.current.scrollIntoView({ block: "end", behavior: "auto" });
    }
  }, [text, isStreaming, autoscroll]);

  return (
    <div
      className={cn("whitespace-pre-wrap break-words leading-relaxed", className)}
      aria-live="polite"
      aria-busy={isStreaming}
    >
      {text}
      {isStreaming ? (
        <span
          ref={endRef}
          aria-hidden
          className={cn("ml-0.5 inline-block w-[0.4em] animate-pulse bg-current align-middle", cursorClassName)}
          style={{ height: "1em" }}
        />
      ) : null}
    </div>
  );
}
