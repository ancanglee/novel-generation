// D4=B: fire-and-forget per event. Band-aid: client-side dedupe + visibility gate.

import { getCsrfToken } from "./csrf";

export type MetricUnit = "Milliseconds" | "Count" | "None";

export interface TelemetryPayload {
  name: string;
  unit: MetricUnit;
  value: number;
  route?: string;
  attrs?: Record<string, string | number | boolean>;
}

const seenKeys = new Set<string>();

function makeKey(p: TelemetryPayload): string {
  return `${p.name}:${p.route ?? ""}:${JSON.stringify(p.attrs ?? {})}`;
}

function isVisible(): boolean {
  if (typeof document === "undefined") return true;
  return document.visibilityState !== "hidden";
}

export function emit(metric: TelemetryPayload): void {
  if (!isVisible()) return; // defer hidden-tab spam (lost is acceptable)
  const body = JSON.stringify(metric);
  if (typeof navigator !== "undefined" && navigator.sendBeacon?.(
    "/telemetry",
    new Blob([body], { type: "application/json" }),
  )) {
    return;
  }
  // Fallback: fetch keepalive
  void fetch("/telemetry", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCsrfToken(),
    },
    body,
    keepalive: true,
  }).catch(() => {
    /* swallow */
  });
}

/** Dedupe helper: emits once per unique key for the lifetime of this browsing session. */
export function emitOnce(metric: TelemetryPayload): void {
  const key = makeKey(metric);
  if (seenKeys.has(key)) return;
  seenKeys.add(key);
  emit(metric);
}
