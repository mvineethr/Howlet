import { createDarkTheme, createLightTheme, type Theme } from "@fluentui/react-components";
import { brandRamp, FONT_MONO, FONT_TEXT, SURFACES } from "./tokens";

export type ThemeMode = "system" | "light" | "dark";

export function resolveMode(mode: ThemeMode, prefersDark: boolean): "light" | "dark" {
  if (mode === "system") return prefersDark ? "dark" : "light";
  return mode;
}

export function buildTheme(dark: boolean, accent: string): Theme {
  const brand = brandRamp(accent);
  const base = dark ? createDarkTheme(brand) : createLightTheme(brand);
  const s = dark ? SURFACES.dark : SURFACES.light;
  return {
    ...base,
    // Fluent's documented dark-mode fix: brand text needs lighter shades.
    ...(dark ? { colorBrandForeground1: brand[110], colorBrandForeground2: brand[120] } : {}),
    fontFamilyBase: FONT_TEXT,
    fontFamilyMonospace: FONT_MONO,
    colorNeutralBackground1: s.panel,
    colorNeutralBackground2: s.bg,
    colorNeutralBackground3: s.elev1,
    colorNeutralForeground1: s.text,
    colorNeutralForeground3: s.dim,
    colorNeutralStroke1: s.border,
    colorNeutralStroke2: s.hair,
  };
}

/** Mirror the tokens into CSS variables for plain CSS and KLineChart. */
export function applyCssVars(dark: boolean, accent: string): void {
  const s = dark ? SURFACES.dark : SURFACES.light;
  const root = document.documentElement.style;
  const vars: Record<string, string> = {
    "--bg": s.bg, "--panel": s.panel, "--elev-1": s.elev1, "--elev-2": s.elev2,
    "--hair": s.hair, "--border": s.border, "--text": s.text, "--dim": s.dim,
    "--up": s.up, "--down": s.down, "--cyan": s.cyan, "--accent": accent,
    "--font-text": FONT_TEXT, "--font-mono": FONT_MONO,
  };
  for (const [k, v] of Object.entries(vars)) root.setProperty(k, v);
  document.documentElement.style.colorScheme = dark ? "dark" : "light";
}
