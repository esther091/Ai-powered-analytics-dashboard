import { createContext, useContext } from "react";

// Validated reference palette (categorical order is the colour-blind-safety
// mechanism: keep it fixed, never cycle). Dark steps are selected, not flipped.
const light = {
  surface: "#fcfcfb",
  grid: "#e7e6e2",
  axis: "#6b6a66",
  text: "#0b0b0b",
  muted: "#52514e",
  series: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
  seq: ["#f0efec", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
  band: "#2a78d6",
  good: "#0ca30c",
  warning: "#fab219",
  serious: "#ec835a",
  critical: "#d03b3b",
};

const dark: typeof light = {
  surface: "#1a1a19",
  grid: "#2f2f2d",
  axis: "#9b9a94",
  text: "#ffffff",
  muted: "#c3c2b7",
  series: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
  seq: ["#262624", "#0d366b", "#104281", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#b7d3f6"],
  band: "#3987e5",
  good: "#0ca30c",
  warning: "#fab219",
  serious: "#ec835a",
  critical: "#d03b3b",
};

export type Palette = typeof light;
export const palettes = { light, dark };
export const ThemeContext = createContext<Palette>(light);
export const usePalette = () => useContext(ThemeContext);

/** Colour follows the entity, not its rank: fixed slot per known segment. */
export const SEGMENT_SLOT: Record<string, number> = {
  Champions: 0,
  Loyal: 2,
  "New & promising": 3,
  "Needs attention": 4,
  "At risk": 1,
  Hibernating: 6,
};

export function seqColor(p: Palette, t: number): string {
  if (!Number.isFinite(t) || t <= 0) return p.seq[0];
  const i = Math.min(p.seq.length - 1, 1 + Math.floor(t * (p.seq.length - 1)));
  return p.seq[i];
}
