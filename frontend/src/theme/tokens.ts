import type { BrandVariants } from "@fluentui/react-components";

// The ONLY file allowed to contain colour literals (CLAUDE.md rule).
export const AMBER = "#eaa53e"; // Howlet brand: hue 36, 80% saturation

export type Surface = {
  bg: string; panel: string; elev1: string; elev2: string; hair: string;
  border: string; text: string; dim: string; up: string; down: string; cyan: string;
};

export const SURFACES: { dark: Surface; light: Surface } = {
  dark: {
    bg: "#1c1c1c", panel: "#202020", elev1: "#2b2b2b", elev2: "#323232",
    hair: "#2d2d2d", border: "#3a3a3a", text: "#e6e6e6", dim: "#9a9a9a",
    up: "#6ccb5f", down: "#ff99a4", cyan: "#60cdff",
  },
  // Calm paper-and-ink light theme, matching the Trading Research Space:
  // warm off-white background, white panels, hairline warm-grey strokes,
  // ink text. Dark surfaces are untouched.
  light: {
    bg: "#faf9f7", panel: "#ffffff", elev1: "#f4f2ef", elev2: "#eeebe6",
    hair: "#e8e4dd", border: "#d8d3c8", text: "#1d1a16", dim: "#6f6a5f",
    up: "#0f7b0f", down: "#c42b1c", cyan: "#005fb8",
  },
};

// Accent choices offered in Settings (AMBER first = default).
export const ACCENT_SWATCHES = [AMBER, "#60cdff", "#6ccb5f", "#ff99a4", "#c3a6ff"];

// Calm card shadow: cards read as hairline-bordered paper, not lifted panels.
export const CALM_SHADOW_4 = "0 1px 2px rgba(0,0,0,0.06), 0 0 1px rgba(0,0,0,0.08)";

export const FONT_TEXT = '"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif';
export const FONT_MONO = '"Cascadia Mono", Consolas, monospace';

function hexToHsl(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  const r = ((n >> 16) & 255) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2;
  if (max === min) return [0, 0, l];
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  const h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return [h / 6, s, l];
}

function hslToHex(h: number, s: number, l: number): string {
  const f = (n: number) => {
    const k = (n + h * 12) % 12;
    const a = s * Math.min(l, 1 - l);
    const c = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
    return Math.round(c * 255).toString(16).padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

const RAMP_L = [0.07, 0.1, 0.14, 0.18, 0.22, 0.27, 0.32, 0.38, 0.44, 0.5, 0.56, 0.63, 0.7, 0.78, 0.86, 0.93];

/** Fluent brand ramp (10 = darkest, 160 = lightest) holding the accent's hue and saturation. */
export function brandRamp(hex: string): BrandVariants {
  const [h, s] = hexToHsl(hex);
  const ramp: Record<number, string> = {};
  RAMP_L.forEach((l, i) => { ramp[(i + 1) * 10] = hslToHex(h, s, l); });
  return ramp as unknown as BrandVariants;
}
