import { create } from "zustand";

export type RangePreset = "1h" | "24h" | "7d" | "30d" | "custom";

interface MonitoringRangeState {
  preset: RangePreset;
  from: string;
  to: string;
  set(preset: RangePreset, from?: string, to?: string): void;
}

function presetWindow(preset: RangePreset): { from: string; to: string } {
  const now = new Date();
  const to = now.toISOString();
  const shift = { "1h": 1, "24h": 24, "7d": 24 * 7, "30d": 24 * 30, custom: 24 }[preset] ?? 24;
  const from = new Date(now.getTime() - shift * 3600 * 1000).toISOString();
  return { from, to };
}

const defaultRange = presetWindow("24h");

export const useMonitoringRangeStore = create<MonitoringRangeState>((set) => ({
  preset: "24h",
  from: defaultRange.from,
  to: defaultRange.to,
  set: (preset, from, to) => {
    if (preset === "custom" && from && to) {
      set({ preset, from, to });
      return;
    }
    const window = presetWindow(preset);
    set({ preset, ...window });
  },
}));
