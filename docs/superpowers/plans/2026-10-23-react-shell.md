# Howlet React Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the new React + Fluent UI shell at `/`: rail, theme, settings, Ctrl+K command box, alerts bell, a customizable Home with 4 blocks, and a stock page Overview with 🦉 chips. The old dashboard keeps working at `/classic`.

**Architecture:** A Vite + React + TypeScript app in `frontend/` builds into `src/howlet/static/app/`, which Flask serves at `/`. The Python API is unchanged. Each block owns its data through a `useApi` hook, and all colour comes from `frontend/src/theme/tokens.ts`. This is plan 1 of 2 for the redesign spec (`docs/superpowers/specs/2026-10-23-react-redesign-design.md`). Plan 2 ports the remaining pages and blocks and deletes `/classic`.

**Tech Stack:** React 18, TypeScript 5, Vite 5, `@fluentui/react-components` v9, `react-grid-layout` 1.4, `zustand` 4, Vitest 2 + jsdom + Testing Library. Python side: Flask (existing), pytest.

## Global Constraints

- No change to `views.py`, the MCP server, the CLI or any `/api/*` route. Only `/` changes, and `/classic` is added.
- Colour hex literals may appear **only** in `frontend/src/theme/tokens.ts`.
- The Python runtime needs no Node: built files under `src/howlet/static/app/` are committed.
- Existing localStorage keys are **read, never rewritten in an incompatible shape**: `howlet_layout_v1`, `howlet_layouts_v1`, `howlet_watchlists_v1`, `howlet_watchlist`, `howlet_pf_holdings`, `howlet_price_alerts_v1`, `howlet_seen_filings_v1`, `howlet_mkts_mode`. New state goes in new keys: `howlet_settings_v1` and `howlet_home_v1`.
- Fonts are system only: text uses `"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif`, and numbers use `"Cascadia Mono", Consolas, monospace` with `font-variant-numeric: tabular-nums`.
- Market, news and crypto failures degrade quietly ("Unavailable, retrying"). Only SEC-backed blocks show error text.
- Motion is disabled under `prefers-reduced-motion: reduce`.
- Commands run from `frontend/` unless stated otherwise. Python tests run from the repo root with `PYTHONPATH=src pytest tests/ -q`, because the editable install on this machine is broken (CLAUDE.md gotcha).
- **Origin note:** the Vite dev server (port 5173) is a different origin from Flask (8813), so it has **separate localStorage**. Your real data only shows at `http://localhost:8813/`. Final verification always happens there.

## File structure

```
frontend/
  package.json, tsconfig.json, vite.config.ts, index.html
  src/
    main.tsx              # mounts <App/>, error boundary
    App.tsx               # FluentProvider + shell layout + page switch
    theme/tokens.ts       # ONLY place with hex colours; brandRamp(); fonts
    theme/theme.ts        # buildTheme(mode, accent) -> Fluent Theme; applyCssVars()
    lib/storage.ts        # safe JSON localStorage read/write
    lib/settings.ts       # Settings type, DEFAULTS, mergeSettings(), useSettings store
    lib/api.ts            # typed fetch wrappers for the routes the shell uses
    lib/useApi.ts         # per-block data hook with its own refresh timer
    lib/route.ts          # hash <-> Route parse/format, useRoute store
    lib/commands.ts       # parseCommand(text) -> Command
    lib/legacy.ts         # read legacy watchlists; migrate old Home layout
    lib/alerts.ts         # price-alert rule evaluation (pure)
    shell/Rail.tsx, shell/TopBar.tsx, shell/CommandBox.tsx, shell/AlertsBell.tsx
    blocks/registry.tsx   # block types -> components; first-run layout
    blocks/Block.tsx      # card chrome: title, loading/error/stale, remove
    blocks/WatchlistBlock.tsx, SmartMoneyBlock.tsx, PulseBlock.tsx, NewsBlock.tsx
    pages/HomePage.tsx, StockPage.tsx, SettingsPage.tsx, PlaceholderPage.tsx
    components/OwlChips.tsx, components/Num.tsx
  src/**/*.test.ts(x)     # Vitest, next to the code
src/howlet/dashboard.py   # "/" -> static/app/index.html, "/classic" -> dashboard.html
src/howlet/static/app/    # build output (committed)
tests/test_dashboard.py   # + route test
pyproject.toml            # package-data includes static/app/**
```

---

### Task 1: Scaffold the frontend and serve it from Flask

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/vite-env.d.ts`
- Modify: `src/howlet/dashboard.py` (the `index` route near line 55), `pyproject.toml:42-43`
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Produces: `npm run build` → `src/howlet/static/app/index.html` + `assets/*`. Flask serves `/` (new app) and `/classic` (old page). `npm test` runs Vitest.

- [ ] **Step 1: Write the failing Python route test**

In `tests/test_dashboard.py`, **replace** `test_index_serves_terminal_html` (around line 96; it asserts `/` contains `HOWLET`, which stops being true) with this test. It uses the file's existing `api` fixture (a Flask test client):

```python
def test_root_serves_react_app_and_classic_serves_old_page(api):
    root = api.get("/")
    assert root.status_code == 200
    assert b'<div id="root">' in root.data

    classic = api.get("/classic")
    assert classic.status_code == 200
    assert b"HOWLET" in classic.data
```

- [ ] **Step 2: Run it to see it fail**

Run (repo root): `PYTHONPATH=src pytest tests/test_dashboard.py -q -k react_app`
Expected: FAIL, because `/` still returns the old page with no `<div id="root">`.

- [ ] **Step 3: Create `frontend/package.json`**

```json
{
  "name": "howlet-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "@fluentui/react-components": "^9.54.0",
    "@fluentui/react-icons": "^2.0.250",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-grid-layout": "^1.4.4",
    "zustand": "^4.5.5"
  },
  "devDependencies": {
    "@testing-library/react": "^16.0.1",
    "@types/react": "^18.3.11",
    "@types/react-dom": "^18.3.1",
    "@types/react-grid-layout": "^1.3.5",
    "@vitejs/plugin-react": "^4.3.3",
    "jsdom": "^25.0.1",
    "typescript": "^5.6.3",
    "vite": "^5.4.10",
    "vitest": "^2.1.4"
  }
}
```

- [ ] **Step 4: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "skipLibCheck": true,
    "types": ["vitest/globals"]
  },
  "include": ["src"]
}
```

- [ ] **Step 5: Create `frontend/vite.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/static/app/",
  build: { outDir: "../src/howlet/static/app", emptyOutDir: true },
  server: { proxy: { "/api": "http://localhost:8813" } },
  test: { environment: "jsdom", globals: true },
});
```

- [ ] **Step 6: Create `frontend/index.html`, `src/vite-env.d.ts`, `src/main.tsx` and a minimal `src/App.tsx`**

`frontend/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="icon" href="/static/logo.png" />
    <title>Howlet</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/src/vite-env.d.ts`:
```ts
/// <reference types="vite/client" />
```

`frontend/src/main.tsx`:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

`frontend/src/App.tsx` (temporary; Task 5 replaces it):
```tsx
export default function App() {
  return <div>Howlet</div>;
}
```

- [ ] **Step 7: Install and build**

Run: `npm install`, then `npm run build`
Expected: `src/howlet/static/app/index.html` exists and references `/static/app/assets/index-*.js`.

- [ ] **Step 8: Point Flask at the build**

In `src/howlet/dashboard.py`, next to `_HTML_PATH`, add:
```python
_APP_INDEX = Path(__file__).parent / "static" / "app" / "index.html"
```
Replace the `index` route with:
```python
    @app.get("/")
    def index() -> Response:
        # The React build; fall back to the classic page if it was never built.
        path = _APP_INDEX if _APP_INDEX.exists() else _HTML_PATH
        return Response(path.read_text(encoding="utf-8"), mimetype="text/html")

    @app.get("/classic")
    def classic() -> Response:
        return Response(_HTML_PATH.read_text(encoding="utf-8"), mimetype="text/html")
```

In `pyproject.toml` replace `howlet = ["dashboard.html", "static/*"]` with:
```toml
howlet = ["dashboard.html", "static/*", "static/app/*", "static/app/assets/*"]
```

- [ ] **Step 9: Run Python tests**

Run (repo root): `PYTHONPATH=src pytest tests/ -q`
Expected: all pass (150; one test was replaced, so the count is unchanged).

- [ ] **Step 10: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html frontend/src src/howlet/static/app src/howlet/dashboard.py pyproject.toml tests/test_dashboard.py
git commit -m "Frontend: scaffold React app, serve at /, old UI at /classic"
```

---

### Task 2: Tokens and Fluent theme

**Files:**
- Create: `frontend/src/theme/tokens.ts`, `frontend/src/theme/theme.ts`
- Test: `frontend/src/theme/theme.test.ts`

**Interfaces:**
- Produces:
  - `tokens.ts`: `AMBER: string`; `ACCENT_SWATCHES: string[]`; `SURFACES: {dark: Surface; light: Surface}`, where `Surface = {bg, panel, elev1, elev2, hair, border, text, dim, up, down, cyan: string}`; `FONT_TEXT: string`; `FONT_MONO: string`; `brandRamp(hex: string): BrandVariants` (keys 10..160).
  - `theme.ts`: `type ThemeMode = "system" | "light" | "dark"`; `resolveMode(mode: ThemeMode, prefersDark: boolean): "light" | "dark"`; `buildTheme(dark: boolean, accent: string): Theme`; `applyCssVars(dark: boolean, accent: string): void`, which writes `--bg`, `--panel`, ..., `--accent` to `document.documentElement`.

- [ ] **Step 1: Write the failing test**

`frontend/src/theme/theme.test.ts`:
```ts
import { brandRamp, AMBER } from "./tokens";
import { buildTheme, resolveMode, applyCssVars } from "./theme";

const lightness = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  return (Math.max(r, g, b) + Math.min(r, g, b)) / 2;
};

test("brandRamp has 16 shades, dark to light", () => {
  const ramp = brandRamp(AMBER);
  const keys = Object.keys(ramp).map(Number);
  expect(keys).toEqual([10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160]);
  const ls = keys.map((k) => lightness((ramp as Record<number, string>)[k]));
  for (let i = 1; i < ls.length; i++) expect(ls[i]).toBeGreaterThan(ls[i - 1]);
});

test("resolveMode follows Windows only in system mode", () => {
  expect(resolveMode("system", true)).toBe("dark");
  expect(resolveMode("system", false)).toBe("light");
  expect(resolveMode("light", true)).toBe("light");
  expect(resolveMode("dark", false)).toBe("dark");
});

test("buildTheme uses Segoe UI and brand-coloured foreground in dark", () => {
  const t = buildTheme(true, AMBER);
  expect(t.fontFamilyBase).toContain("Segoe UI");
  expect(t.fontFamilyMonospace).toContain("Cascadia Mono");
  expect(t.colorBrandForeground1).toBe(brandRamp(AMBER)[110]);
});

test("applyCssVars writes tokens onto :root", () => {
  applyCssVars(true, AMBER);
  const s = document.documentElement.style;
  expect(s.getPropertyValue("--accent")).toBe(AMBER);
  expect(s.getPropertyValue("--up")).not.toBe("");
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npx vitest run src/theme`
Expected: FAIL, "Cannot find module './tokens'".

- [ ] **Step 3: Implement `tokens.ts`**

```ts
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
  light: {
    bg: "#f3f3f3", panel: "#fbfbfb", elev1: "#ffffff", elev2: "#f9f9f9",
    hair: "#ebebeb", border: "#d1d1d1", text: "#1b1b1b", dim: "#616161",
    up: "#0f7b0f", down: "#c42b1c", cyan: "#005fb8",
  },
};

// Accent choices offered in Settings (AMBER first = default).
export const ACCENT_SWATCHES = [AMBER, "#60cdff", "#6ccb5f", "#ff99a4", "#c3a6ff"];

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
```

- [ ] **Step 4: Implement `theme.ts`**

```ts
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
```

- [ ] **Step 5: Run the tests**

Run: `npx vitest run src/theme`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/theme
git commit -m "Frontend: colour tokens and Fluent theme with amber brand ramp"
```

---

### Task 3: Safe storage and the settings store

**Files:**
- Create: `frontend/src/lib/storage.ts`, `frontend/src/lib/settings.ts`
- Test: `frontend/src/lib/settings.test.ts`

**Interfaces:**
- Consumes: `ThemeMode` from `theme/theme.ts`, `AMBER` from `theme/tokens.ts`.
- Produces:
  - `storage.ts`: `readJson<T>(key: string, fallback: T, valid: (v: unknown) => v is T): T`; `writeJson(key: string, value: unknown): void`.
  - `settings.ts`: `type PageId = "home" | "markets" | "smart" | "screener" | "news" | "portfolio" | "settings"`; `PAGE_IDS: PageId[]` (default rail order); `type Settings = { version: 1; themeMode: ThemeMode; accent: string; density: "comfortable" | "compact"; textSize: "small" | "medium" | "large"; railOrder: PageId[]; railHidden: PageId[]; startPage: PageId; chartRange: string; indicators: string[]; refresh: "fast" | "normal" | "slow"; alertSound: boolean; showOptions: boolean }`; `DEFAULT_SETTINGS: Settings`; `SETTINGS_KEY = "howlet_settings_v1"`; `mergeSettings(raw: unknown): Settings`; `REFRESH_MS: Record<Settings["refresh"], number>`; `useSettings` (zustand store with `settings` and `update(patch: Partial<Settings>)`).

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/settings.test.ts`:
```ts
import { DEFAULT_SETTINGS, mergeSettings, PAGE_IDS, SETTINGS_KEY, useSettings } from "./settings";
import { readJson } from "./storage";

beforeEach(() => localStorage.clear());

test("garbage falls back to defaults", () => {
  expect(mergeSettings("nope")).toEqual(DEFAULT_SETTINGS);
  expect(mergeSettings(null)).toEqual(DEFAULT_SETTINGS);
});

test("known fields are kept, unknown and badly typed ones dropped", () => {
  const s = mergeSettings({ themeMode: "dark", density: "huge", junk: 1, alertSound: false });
  expect(s.themeMode).toBe("dark");
  expect(s.density).toBe(DEFAULT_SETTINGS.density);
  expect(s.alertSound).toBe(false);
  expect((s as Record<string, unknown>).junk).toBeUndefined();
});

test("railOrder always contains every page exactly once", () => {
  const s = mergeSettings({ railOrder: ["news", "news", "bogus", "home"] });
  expect(s.railOrder.slice(0, 2)).toEqual(["news", "home"]);
  expect([...s.railOrder].sort()).toEqual([...PAGE_IDS].sort());
});

test("home and settings can never be hidden", () => {
  const s = mergeSettings({ railHidden: ["home", "settings", "news"] });
  expect(s.railHidden).toEqual(["news"]);
});

test("update persists to localStorage", () => {
  useSettings.getState().update({ accent: "#3b82f6" });
  expect(readJson(SETTINGS_KEY, null, (v): v is object => typeof v === "object")).toMatchObject({ accent: "#3b82f6" });
});

test("readJson survives corrupt JSON", () => {
  localStorage.setItem("x", "{not json");
  expect(readJson("x", 5, (v): v is number => typeof v === "number")).toBe(5);
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npx vitest run src/lib/settings`
Expected: FAIL, "Cannot find module './settings'".

- [ ] **Step 3: Implement `storage.ts`**

```ts
export function readJson<T>(key: string, fallback: T, valid: (v: unknown) => v is T): T {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null) return fallback;
    const v: unknown = JSON.parse(raw);
    return valid(v) ? v : fallback;
  } catch {
    return fallback; // corrupt JSON or storage blocked: never white-screen
  }
}

export function writeJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage full or blocked: settings just won't persist */
  }
}
```

- [ ] **Step 4: Implement `settings.ts`**

```ts
import { create } from "zustand";
import type { ThemeMode } from "../theme/theme";
import { AMBER } from "../theme/tokens";
import { readJson, writeJson } from "./storage";

export type PageId = "home" | "markets" | "smart" | "screener" | "news" | "portfolio" | "settings";
export const PAGE_IDS: PageId[] = ["home", "markets", "smart", "screener", "news", "portfolio", "settings"];
const UNHIDEABLE: PageId[] = ["home", "settings"];

export type Settings = {
  version: 1;
  themeMode: ThemeMode;
  accent: string;
  density: "comfortable" | "compact";
  textSize: "small" | "medium" | "large";
  railOrder: PageId[];
  railHidden: PageId[];
  startPage: PageId;
  chartRange: string;
  indicators: string[];
  refresh: "fast" | "normal" | "slow";
  alertSound: boolean;
  showOptions: boolean;
};

export const SETTINGS_KEY = "howlet_settings_v1";
export const REFRESH_MS: Record<Settings["refresh"], number> = { fast: 15_000, normal: 60_000, slow: 300_000 };

export const DEFAULT_SETTINGS: Settings = {
  version: 1,
  themeMode: "system",
  accent: AMBER,
  density: "comfortable",
  textSize: "medium",
  railOrder: PAGE_IDS,
  railHidden: [],
  startPage: "home",
  chartRange: "6mo",
  indicators: ["MA"],
  refresh: "normal",
  alertSound: true,
  showOptions: false,
};

const oneOf = <T extends string>(v: unknown, allowed: readonly T[], d: T): T =>
  typeof v === "string" && (allowed as readonly string[]).includes(v) ? (v as T) : d;
const isPage = (v: unknown): v is PageId => typeof v === "string" && (PAGE_IDS as string[]).includes(v);

export function mergeSettings(raw: unknown): Settings {
  const r = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const d = DEFAULT_SETTINGS;
  const order = Array.isArray(r.railOrder) ? [...new Set(r.railOrder.filter(isPage))] : [];
  const hidden = Array.isArray(r.railHidden)
    ? [...new Set(r.railHidden.filter(isPage))].filter((p) => !UNHIDEABLE.includes(p))
    : d.railHidden;
  return {
    version: 1,
    themeMode: oneOf(r.themeMode, ["system", "light", "dark"] as const, d.themeMode),
    accent: typeof r.accent === "string" && /^#[0-9a-f]{6}$/i.test(r.accent) ? r.accent : d.accent,
    density: oneOf(r.density, ["comfortable", "compact"] as const, d.density),
    textSize: oneOf(r.textSize, ["small", "medium", "large"] as const, d.textSize),
    railOrder: [...order, ...PAGE_IDS.filter((p) => !order.includes(p))],
    railHidden: hidden,
    startPage: isPage(r.startPage) ? r.startPage : d.startPage,
    chartRange: typeof r.chartRange === "string" ? r.chartRange : d.chartRange,
    indicators: Array.isArray(r.indicators) ? r.indicators.filter((x): x is string => typeof x === "string") : d.indicators,
    refresh: oneOf(r.refresh, ["fast", "normal", "slow"] as const, d.refresh),
    alertSound: typeof r.alertSound === "boolean" ? r.alertSound : d.alertSound,
    showOptions: typeof r.showOptions === "boolean" ? r.showOptions : d.showOptions,
  };
}

type Store = { settings: Settings; update: (patch: Partial<Settings>) => void };

export const useSettings = create<Store>((set, get) => ({
  settings: mergeSettings(readJson<unknown>(SETTINGS_KEY, null, (v): v is unknown => true)),
  update: (patch) => {
    const settings = mergeSettings({ ...get().settings, ...patch });
    writeJson(SETTINGS_KEY, settings);
    set({ settings });
  },
}));
```

- [ ] **Step 5: Run the tests**

Run: `npx vitest run src/lib/settings`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/storage.ts frontend/src/lib/settings.ts frontend/src/lib/settings.test.ts
git commit -m "Frontend: crash-proof storage and settings store"
```

---

### Task 4: API client and the per-block data hook

**Files:**
- Create: `frontend/src/lib/api.ts`, `frontend/src/lib/useApi.ts`
- Test: `frontend/src/lib/api.test.ts`

**Interfaces:**
- Produces:
  - `api.ts`: `class ApiError extends Error { status: number }`; `getJson<T>(path: string): Promise<T>`, which throws `ApiError` with the server's `{"error": ...}` text on non-2xx; the types `Quote`, `TapeRow`, `NewsItem`, `DiffResult`, `HoldersResult`, `ManagerRef`, `Security`; and the wrappers `api.quotes(symbols)`, `api.tape()`, `api.news(limit)`, `api.diff(manager)`, `api.holders(symbol)`, `api.managers()`, `api.security(symbol)`.
  - `useApi.ts`: `useApi<T>(key: string | null, fetcher: () => Promise<T>, refreshMs?: number): { data: T | undefined; error: ApiError | Error | undefined; loading: boolean; fetchedAt: number | undefined; reload: () => void }`. A `null` key means don't fetch. A failed refresh keeps the last data and sets `error`.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/api.test.ts`:
```ts
import { renderHook, waitFor, act } from "@testing-library/react";
import { ApiError, getJson } from "./api";
import { useApi } from "./useApi";

afterEach(() => vi.restoreAllMocks());

test("getJson surfaces the server's JSON error text", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ error: "Upstream request failed: boom" }), { status: 502 }),
  );
  await expect(getJson("/api/x")).rejects.toMatchObject({ status: 502, message: "Upstream request failed: boom" });
  await expect(getJson("/api/x")).rejects.toBeInstanceOf(ApiError);
});

test("useApi keeps last good data when a refresh fails", async () => {
  let n = 0;
  const fetcher = () => (++n === 1 ? Promise.resolve(42) : Promise.reject(new Error("down")));
  const { result } = renderHook(() => useApi("k", fetcher));
  await waitFor(() => expect(result.current.data).toBe(42));
  act(() => result.current.reload());
  await waitFor(() => expect(result.current.error?.message).toBe("down"));
  expect(result.current.data).toBe(42);
});

test("useApi with a null key does not fetch", () => {
  const fetcher = vi.fn(() => Promise.resolve(1));
  renderHook(() => useApi(null, fetcher));
  expect(fetcher).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npx vitest run src/lib/api`
Expected: FAIL, "Cannot find module './api'".

- [ ] **Step 3: Implement `api.ts`**

Field names are copied from `views.py` (`_quote_dict`, `tape_view`, `news_view`, `diff_view`, `holders_view`, `managers_view`).

```ts
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  let body: unknown = null;
  try { body = await res.json(); } catch { /* non-JSON body */ }
  if (!res.ok) {
    const msg = body && typeof body === "object" && "error" in body ? String((body as { error: unknown }).error) : `HTTP ${res.status}`;
    throw new ApiError(msg, res.status);
  }
  return body as T;
}

export type Quote = {
  symbol: string; name: string | null; price: number; change: number | null;
  change_pct: number | null; previous_close: number | null; currency: string | null;
  day_low: number | null; day_high: number | null; week52_low: number | null;
  week52_high: number | null; volume: number | null; sparkline?: number[];
};
export type TapeRow = { symbol: string; label: string; price: number; change: number | null; change_pct: number | null };
export type NewsItem = { title: string; link: string; source: string; symbol: string | null; published: string | null };
export type DiffChange = { issuer: string; cusip: string; status: string; value_change_usd: number; shares_change: number; current_value_usd: number };
export type DiffResult = { prior_period: string | null; current_period: string | null; changes: DiffChange[] };
export type Holder = { manager: string; period_of_report: string | null; issuer: string; shares: number; value_usd: number; weight_pct: number };
export type HoldersResult = { symbol: string; tracked_managers: string[]; holders: Holder[] };
export type ManagerRef = { label: string; cik: string };
export type Security = Quote & { long_name?: string | null; exchange?: string | null };

const q = encodeURIComponent;
export const api = {
  quotes: (symbols: string[]) => getJson<Quote[]>(`/api/quotes?symbols=${q(symbols.slice(0, 30).join(","))}`),
  tape: () => getJson<TapeRow[]>("/api/tape"),
  news: (limit = 20) => getJson<NewsItem[]>(`/api/news?limit=${limit}`),
  diff: (manager: string) => getJson<DiffResult>(`/api/diff/${q(manager)}`),
  holders: (symbol: string) => getJson<HoldersResult>(`/api/holders/${q(symbol)}`),
  managers: () => getJson<ManagerRef[]>("/api/managers"),
  security: (symbol: string) => getJson<Security>(`/api/security/${q(symbol)}`),
};
```

- [ ] **Step 4: Implement `useApi.ts`**

```ts
import { useCallback, useEffect, useRef, useState } from "react";

export function useApi<T>(key: string | null, fetcher: () => Promise<T>, refreshMs?: number) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<Error>();
  const [loading, setLoading] = useState(false);
  const [fetchedAt, setFetchedAt] = useState<number>();
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const load = useCallback(() => {
    if (key === null) return;
    setLoading(true);
    fetcherRef.current()
      .then((d) => { setData(d); setError(undefined); setFetchedAt(Date.now()); })
      .catch((e: Error) => setError(e)) // keep last good data on failure
      .finally(() => setLoading(false));
  }, [key]);

  useEffect(() => {
    setData(undefined);
    setError(undefined);
    load();
    if (!refreshMs || key === null) return;
    const id = setInterval(load, refreshMs);
    return () => clearInterval(id);
  }, [key, refreshMs, load]);

  return { data, error, loading, fetchedAt, reload: load };
}
```

- [ ] **Step 5: Run the tests**

Run: `npx vitest run src/lib/api`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/useApi.ts frontend/src/lib/api.test.ts
git commit -m "Frontend: typed API client and per-block useApi hook"
```

---

### Task 5: Routing, rail, top bar and the app shell

**Files:**
- Create: `frontend/src/lib/route.ts`, `frontend/src/shell/Rail.tsx`, `frontend/src/shell/TopBar.tsx`, `frontend/src/pages/PlaceholderPage.tsx`
- Modify: `frontend/src/App.tsx` (full replacement)
- Test: `frontend/src/lib/route.test.ts`

**Interfaces:**
- Consumes: `useSettings`, `PageId`, `Settings` (Task 3); `buildTheme`, `resolveMode`, `applyCssVars` (Task 2).
- Produces:
  - `route.ts`: `type Route = { kind: "page"; page: PageId } | { kind: "stock"; symbol: string; tab: StockTab }`; `type StockTab = "overview" | "chart" | "financials" | "holders" | "news" | "options"`; `parseHash(hash: string, fallback: PageId): Route`; `formatRoute(r: Route): string`; `useRoute` (zustand: `route`, `go(r: Route)`; it syncs `location.hash` and listens to `hashchange`); `visibleRail(s: Settings): PageId[]`.
  - `App.tsx`: renders `<TopBar/>`, `<Rail/>` and the page for the current route. Ctrl+1..7 jump to the Nth visible rail page.
  - `PlaceholderPage({ title }: { title: string })`: "Coming in the next update", with a link to `/classic`.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/route.test.ts`:
```ts
import { formatRoute, parseHash, visibleRail } from "./route";
import { DEFAULT_SETTINGS } from "./settings";

test("parses pages, stocks and junk", () => {
  expect(parseHash("#/news", "home")).toEqual({ kind: "page", page: "news" });
  expect(parseHash("#/stock/brk-b", "home")).toEqual({ kind: "stock", symbol: "BRK-B", tab: "overview" });
  expect(parseHash("#/stock/AAPL/holders", "home")).toEqual({ kind: "stock", symbol: "AAPL", tab: "holders" });
  expect(parseHash("#/stock/AAPL/bogus", "home")).toEqual({ kind: "stock", symbol: "AAPL", tab: "overview" });
  expect(parseHash("", "markets")).toEqual({ kind: "page", page: "markets" });
  expect(parseHash("#/nope", "home")).toEqual({ kind: "page", page: "home" });
});

test("format round-trips", () => {
  const r = { kind: "stock", symbol: "^GSPC", tab: "chart" } as const;
  expect(parseHash(formatRoute(r), "home")).toEqual(r);
});

test("visibleRail respects order and hidden pages", () => {
  const s = { ...DEFAULT_SETTINGS, railOrder: ["news", ...DEFAULT_SETTINGS.railOrder.filter((p) => p !== "news")], railHidden: ["screener" as const] };
  const rail = visibleRail(s);
  expect(rail[0]).toBe("news");
  expect(rail).not.toContain("screener");
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npx vitest run src/lib/route`
Expected: FAIL, "Cannot find module './route'".

- [ ] **Step 3: Implement `route.ts`**

```ts
import { create } from "zustand";
import { PAGE_IDS, useSettings, type PageId, type Settings } from "./settings";

export type StockTab = "overview" | "chart" | "financials" | "holders" | "news" | "options";
const STOCK_TABS: StockTab[] = ["overview", "chart", "financials", "holders", "news", "options"];
export type Route = { kind: "page"; page: PageId } | { kind: "stock"; symbol: string; tab: StockTab };

export function parseHash(hash: string, fallback: PageId): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "stock" && parts[1]) {
    const tab = (STOCK_TABS as string[]).includes(parts[2]) ? (parts[2] as StockTab) : "overview";
    return { kind: "stock", symbol: parts[1].toUpperCase(), tab };
  }
  const page = (PAGE_IDS as string[]).includes(parts[0]) ? (parts[0] as PageId) : fallback;
  return { kind: "page", page: parts.length ? page : fallback };
}

export function formatRoute(r: Route): string {
  return r.kind === "page" ? `#/${r.page}` : `#/stock/${encodeURIComponent(r.symbol)}/${r.tab}`;
}

export function visibleRail(s: Settings): PageId[] {
  return s.railOrder.filter((p) => !s.railHidden.includes(p));
}

type RouteStore = { route: Route; go: (r: Route) => void };
export const useRoute = create<RouteStore>((set) => ({
  route: parseHash(location.hash, useSettings.getState().settings.startPage),
  go: (r) => { location.hash = formatRoute(r); set({ route: r }); },
}));

window.addEventListener("hashchange", () => {
  useRoute.setState({ route: parseHash(location.hash, useSettings.getState().settings.startPage) });
});
```

The BACK button is the browser's own Back, which works because every navigation changes the hash.

- [ ] **Step 4: Implement `PlaceholderPage.tsx`, `Rail.tsx` and `TopBar.tsx`**

`frontend/src/pages/PlaceholderPage.tsx`:
```tsx
import { Body1, Link, Title3 } from "@fluentui/react-components";

export default function PlaceholderPage({ title }: { title: string }) {
  return (
    <div style={{ padding: 24 }}>
      <Title3>{title}</Title3>
      <Body1 block style={{ marginTop: 8 }}>
        Coming in the next update. Until then it lives in the <Link href="/classic">classic view</Link>.
      </Body1>
    </div>
  );
}
```

`frontend/src/shell/Rail.tsx`:
```tsx
import { Tooltip, makeStyles, tokens } from "@fluentui/react-components";
import {
  Home24Regular, ArrowTrending24Regular, PeopleTeam24Regular, Filter24Regular,
  News24Regular, Briefcase24Regular, Settings24Regular,
} from "@fluentui/react-icons";
import type { JSX } from "react";
import { useSettings, type PageId } from "../lib/settings";
import { useRoute, visibleRail } from "../lib/route";

export const PAGE_META: Record<PageId, { label: string; icon: JSX.Element }> = {
  home: { label: "Home", icon: <Home24Regular /> },
  markets: { label: "Markets", icon: <ArrowTrending24Regular /> },
  smart: { label: "Smart Money", icon: <PeopleTeam24Regular /> },
  screener: { label: "Screener", icon: <Filter24Regular /> },
  news: { label: "News", icon: <News24Regular /> },
  portfolio: { label: "Portfolio", icon: <Briefcase24Regular /> },
  settings: { label: "Settings", icon: <Settings24Regular /> },
};

const useStyles = makeStyles({
  rail: {
    width: "56px", display: "flex", flexDirection: "column", alignItems: "center", gap: "4px",
    paddingTop: "8px", backgroundColor: tokens.colorNeutralBackground1,
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  item: {
    width: "40px", height: "36px", display: "flex", alignItems: "center", justifyContent: "center",
    borderRadius: tokens.borderRadiusMedium, border: "none", background: "transparent",
    color: tokens.colorNeutralForeground3, cursor: "pointer",
    ":hover": { backgroundColor: tokens.colorNeutralBackground3 },
  },
  on: { color: tokens.colorBrandForeground1, backgroundColor: tokens.colorNeutralBackground3, boxShadow: `inset 3px 0 0 ${tokens.colorBrandForeground1}` },
  bottom: { marginTop: "auto", marginBottom: "8px" },
});

export default function Rail() {
  const s = useStyles();
  const settings = useSettings((st) => st.settings);
  const { route, go } = useRoute();
  const pages = visibleRail(settings).filter((p) => p !== "settings");
  const item = (p: PageId, extra = "") => {
    const on = route.kind === "page" && route.page === p;
    return (
      <Tooltip key={p} content={PAGE_META[p].label} relationship="label" positioning="after">
        <button className={`${s.item} ${on ? s.on : ""} ${extra}`} aria-current={on ? "page" : undefined}
          onClick={() => go({ kind: "page", page: p })}>{PAGE_META[p].icon}</button>
      </Tooltip>
    );
  };
  return <nav className={s.rail} aria-label="Pages">{pages.map((p) => item(p))}{item("settings", s.bottom)}</nav>;
}
```

`frontend/src/shell/TopBar.tsx` (Task 6 wires in the command box and Task 10 the bell):
```tsx
import { makeStyles, tokens, Text } from "@fluentui/react-components";
import type { ReactNode } from "react";

const useStyles = makeStyles({
  bar: {
    height: "44px", display: "flex", alignItems: "center", gap: "12px", padding: "0 12px",
    backgroundColor: tokens.colorNeutralBackground1, borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  brand: { display: "flex", alignItems: "center", gap: "6px", color: tokens.colorBrandForeground1, fontWeight: 600 },
});

export default function TopBar({ center, right }: { center?: ReactNode; right?: ReactNode }) {
  const s = useStyles();
  return (
    <header className={s.bar}>
      <span className={s.brand}><img src="/static/logo.png" alt="" width={20} height={20} /><Text weight="semibold">Howlet</Text></span>
      <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>{center}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>{right}</div>
    </header>
  );
}
```

- [ ] **Step 5: Replace `App.tsx`**

```tsx
import { FluentProvider } from "@fluentui/react-components";
import { useEffect, useMemo, useState } from "react";
import { buildTheme, resolveMode, applyCssVars } from "./theme/theme";
import { useSettings } from "./lib/settings";
import { useRoute, visibleRail } from "./lib/route";
import Rail, { PAGE_META } from "./shell/Rail";
import TopBar from "./shell/TopBar";
import PlaceholderPage from "./pages/PlaceholderPage";

const prefersDark = () => window.matchMedia("(prefers-color-scheme: dark)").matches;
const TEXT_SCALE = { small: "13px", medium: "14px", large: "16px" } as const;

export default function App() {
  const settings = useSettings((s) => s.settings);
  const { route, go } = useRoute();
  const [osDark, setOsDark] = useState(prefersDark);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = () => setOsDark(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  const dark = resolveMode(settings.themeMode, osDark) === "dark";
  const theme = useMemo(() => buildTheme(dark, settings.accent), [dark, settings.accent]);
  useEffect(() => applyCssVars(dark, settings.accent), [dark, settings.accent]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.ctrlKey || e.altKey || e.metaKey) return;
      const n = Number(e.key);
      const rail = visibleRail(settings);
      if (n >= 1 && n <= rail.length) { e.preventDefault(); go({ kind: "page", page: rail[n - 1] }); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [settings, go]);

  const page = route.kind === "stock"
    ? <PlaceholderPage title={route.symbol} />
    : <PlaceholderPage title={PAGE_META[route.page].label} />;

  return (
    <FluentProvider theme={theme} style={{ height: "100vh", display: "flex", flexDirection: "column", fontSize: TEXT_SCALE[settings.textSize] }}
      data-density={settings.density}>
      <TopBar />
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        <Rail />
        <main style={{ flex: 1, overflow: "auto", background: "var(--bg)" }}>{page}</main>
      </div>
    </FluentProvider>
  );
}
```

- [ ] **Step 6: Run the tests and build**

Run: `npx vitest run`, then `npm run build`
Expected: all tests pass and the build succeeds with no TypeScript errors.

- [ ] **Step 7: Live check**

Start the dashboard (`preview_start` "howlet-dashboard", or `howlet dashboard --port 8813`). Open `http://localhost:8813/`. You should see the rail with 7 icons, and clicking each one changes the hash and the title. Ctrl+2 goes to Markets. Toggle Windows dark/light (Settings → Personalization → Colors) and the app follows. `/classic` still shows the old terminal.

- [ ] **Step 8: Commit**

```bash
git add frontend/src src/howlet/static/app
git commit -m "Frontend: app shell with rail, hash routing, theme following Windows"
```

---

### Task 6: Command parser and the Ctrl+K command box

**Files:**
- Create: `frontend/src/lib/commands.ts`, `frontend/src/lib/alerts.ts`, `frontend/src/shell/CommandBox.tsx`
- Modify: `frontend/src/App.tsx` (pass `<CommandBox/>` as `TopBar center`), `src/howlet/dashboard.html` (one line in `boot()`)
- Test: `frontend/src/lib/commands.test.ts`, `frontend/src/lib/alerts.test.ts`

**Interfaces:**
- Consumes: `Route`, `useRoute` (Task 5); `api.managers` (Task 4); `readJson`, `writeJson` (Task 3).
- Produces:
  - `alerts.ts`: `type PriceAlert = { id: string; sym: string; op: ">" | "<"; px: number; fired: { price: number; at: string } | null }`. This is **the exact shape the classic page stores** under `howlet_price_alerts_v1`, so both UIs share alerts. Also `getAlerts(): PriceAlert[]`; `saveAlerts(a: PriceAlert[]): void`; `addPriceAlert(sym: string, op: ">" | "<", px: number): void`; `removeAlert(id: string): void`; and `evaluate(alerts: PriceAlert[], prices: Record<string, number>, now: string): PriceAlert[]`, which is pure and returns only the newly fired alerts, each with `fired` set.
  - `commands.ts`: `type Command = { kind: "go"; route: Route } | { kind: "manager"; id: string } | { kind: "alert"; symbol: string; op: ">" | "<"; price: number } | { kind: "error"; message: string }`; `parseCommand(text: string, managers: string[]): Command | null` (null for empty input). A manager command routes to Smart Money in plan 2. In this plan it opens `/classic#` with the PORT command, so it isn't a dead end.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/commands.test.ts`:
```ts
import { parseCommand } from "./commands";

const M = ["buffett", "ackman"];

test.each([
  ["AAPL", { kind: "go", route: { kind: "stock", symbol: "AAPL", tab: "overview" } }],
  ["aapl des", { kind: "go", route: { kind: "stock", symbol: "AAPL", tab: "overview" } }],
  ["AAPL GP", { kind: "go", route: { kind: "stock", symbol: "AAPL", tab: "chart" } }],
  ["AAPL FA", { kind: "go", route: { kind: "stock", symbol: "AAPL", tab: "financials" } }],
  ["AAPL HDS", { kind: "go", route: { kind: "stock", symbol: "AAPL", tab: "holders" } }],
  ["AAPL OPT", { kind: "go", route: { kind: "stock", symbol: "AAPL", tab: "options" } }],
  ["news", { kind: "go", route: { kind: "page", page: "news" } }],
  ["MKTS", { kind: "go", route: { kind: "page", page: "markets" } }],
  ["ECO", { kind: "go", route: { kind: "page", page: "markets" } }],
  ["EQS", { kind: "go", route: { kind: "page", page: "screener" } }],
  ["PF", { kind: "go", route: { kind: "page", page: "portfolio" } }],
  ["home", { kind: "go", route: { kind: "page", page: "home" } }],
  ["buffett", { kind: "manager", id: "buffett" }],
  ["ackman port", { kind: "manager", id: "ackman" }],
  ["1067983", { kind: "manager", id: "1067983" }],
  ["alert tsla < 200", { kind: "alert", symbol: "TSLA", op: "<", price: 200 }],
  ["ALERT BRK-B > 532.5", { kind: "alert", symbol: "BRK-B", op: ">", price: 532.5 }],
])("%s", (input, expected) => {
  expect(parseCommand(input, M)).toEqual(expected);
});

test("bad alert syntax explains itself", () => {
  expect(parseCommand("alert tsla", M)).toEqual({ kind: "error", message: "Usage: ALERT AAPL > 350" });
});

test("empty input is null", () => {
  expect(parseCommand("   ", M)).toBeNull();
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npx vitest run src/lib/commands`
Expected: FAIL, "Cannot find module './commands'".

- [ ] **Step 3: Implement `commands.ts`**

```ts
import type { Route, StockTab } from "./route";
import type { PageId } from "./settings";

export type Command =
  | { kind: "go"; route: Route }
  | { kind: "manager"; id: string }
  | { kind: "alert"; symbol: string; op: ">" | "<"; price: number }
  | { kind: "error"; message: string };

const PAGES: Record<string, PageId> = {
  HOME: "home", DASH: "home", MKTS: "markets", WEI: "markets", FXC: "markets", ECO: "markets",
  NEWS: "news", N: "news", TOP: "news", EQS: "screener", PF: "portfolio", MY: "portfolio",
  WATCH: "portfolio", SETTINGS: "settings", HELP: "settings",
};
const FUNCS: Record<string, StockTab> = { DES: "overview", GP: "chart", GIP: "chart", FA: "financials", HDS: "holders", OPT: "options", OMON: "options", CN: "news" };

export function parseCommand(text: string, managers: string[]): Command | null {
  const t = text.trim();
  if (!t) return null;
  const parts = t.split(/\s+/);
  const head = parts[0].toUpperCase();

  if (head === "ALERT") {
    const m = t.match(/^alert\s+([A-Za-z0-9.^=-]+)\s*([<>])\s*(\d+(?:\.\d+)?)$/i);
    return m
      ? { kind: "alert", symbol: m[1].toUpperCase(), op: m[2] as ">" | "<", price: parseFloat(m[3]) }
      : { kind: "error", message: "Usage: ALERT AAPL > 350" };
  }
  if (parts.length === 1 && PAGES[head]) return { kind: "go", route: { kind: "page", page: PAGES[head] } };

  const fn = parts.length > 1 ? parts[parts.length - 1].toUpperCase() : null;
  const subject = fn ? parts.slice(0, -1).join(" ") : t;
  if (fn === "PORT") return { kind: "manager", id: subject.toLowerCase() };
  if (managers.includes(subject.toLowerCase()) || /^\d{4,10}$/.test(subject)) {
    return { kind: "manager", id: subject.toLowerCase() };
  }
  const tab: StockTab = fn && FUNCS[fn] ? FUNCS[fn] : "overview";
  return { kind: "go", route: { kind: "stock", symbol: subject.toUpperCase(), tab } };
}
```

- [ ] **Step 4: Run the tests**

Run: `npx vitest run src/lib/commands`
Expected: 19 passed.

- [ ] **Step 5: Write the failing alerts test**

`frontend/src/lib/alerts.test.ts`:
```ts
import { addPriceAlert, evaluate, getAlerts, removeAlert, type PriceAlert } from "./alerts";

beforeEach(() => localStorage.clear());

const a = (over: Partial<PriceAlert>): PriceAlert => ({ id: "1", sym: "AAPL", op: ">", px: 100, fired: null, ...over });

test("fires only crossed, unfired alerts with a known price", () => {
  const list = [
    a({ id: "1", op: ">", px: 100 }),           // 101 > 100: fires
    a({ id: "2", op: "<", px: 100 }),           // 101 < 100: no
    a({ id: "3", sym: "TSLA" }),                 // no price: no
    a({ id: "4", fired: { price: 1, at: "x" } }), // already fired: no
  ];
  const fired = evaluate(list, { AAPL: 101 }, "2026-10-23T00:00:00Z");
  expect(fired.map((f) => f.id)).toEqual(["1"]);
  expect(fired[0].fired).toEqual({ price: 101, at: "2026-10-23T00:00:00Z" });
});

test("add and remove persist in the classic page's key", () => {
  addPriceAlert("tsla", "<", 200);
  const [x] = getAlerts();
  expect(x).toMatchObject({ sym: "TSLA", op: "<", px: 200, fired: null });
  expect(JSON.parse(localStorage.getItem("howlet_price_alerts_v1")!)).toHaveLength(1);
  removeAlert(x.id);
  expect(getAlerts()).toEqual([]);
});
```

- [ ] **Step 6: Run to see it fail**

Run: `npx vitest run src/lib/alerts`
Expected: FAIL, "Cannot find module './alerts'".

- [ ] **Step 7: Implement `alerts.ts`**

```ts
import { readJson, writeJson } from "./storage";

export type PriceAlert = { id: string; sym: string; op: ">" | "<"; px: number; fired: { price: number; at: string } | null };
const KEY = "howlet_price_alerts_v1"; // shared with the classic page

export const getAlerts = (): PriceAlert[] => readJson<PriceAlert[]>(KEY, [], (v): v is PriceAlert[] => Array.isArray(v));
export const saveAlerts = (a: PriceAlert[]) => writeJson(KEY, a);

export function addPriceAlert(sym: string, op: ">" | "<", px: number): void {
  const id = "w" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  saveAlerts([...getAlerts(), { id, sym: sym.toUpperCase(), op, px, fired: null }]);
}

export function removeAlert(id: string): void {
  saveAlerts(getAlerts().filter((a) => a.id !== id));
}

export function evaluate(alerts: PriceAlert[], prices: Record<string, number>, now: string): PriceAlert[] {
  return alerts
    .filter((a) => !a.fired && typeof prices[a.sym] === "number" && (a.op === ">" ? prices[a.sym] > a.px : prices[a.sym] < a.px))
    .map((a) => ({ ...a, fired: { price: prices[a.sym], at: now } }));
}
```

- [ ] **Step 8: Run the alerts test**

Run: `npx vitest run src/lib/alerts`
Expected: 2 passed.

- [ ] **Step 9: Implement `CommandBox.tsx`**

```tsx
import { Input, Text, makeStyles, tokens } from "@fluentui/react-components";
import { Search20Regular } from "@fluentui/react-icons";
import { useEffect, useRef, useState } from "react";
import { parseCommand } from "../lib/commands";
import { useRoute } from "../lib/route";
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import { addPriceAlert } from "../lib/alerts";

const useStyles = makeStyles({
  box: { width: "min(520px, 60vw)" },
  msg: { marginLeft: "8px", color: tokens.colorNeutralForeground3 },
});

export default function CommandBox() {
  const s = useStyles();
  const ref = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [msg, setMsg] = useState("");
  const go = useRoute((r) => r.go);
  const { data: managers } = useApi("managers", api.managers);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key.toLowerCase() === "k") { e.preventDefault(); ref.current?.focus(); ref.current?.select(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const run = () => {
    const cmd = parseCommand(text, (managers ?? []).map((m) => m.label));
    if (!cmd) return;
    if (cmd.kind === "go") go(cmd.route);
    else if (cmd.kind === "manager") location.href = `/classic?cmd=${encodeURIComponent(cmd.id + " PORT")}`;
    else if (cmd.kind === "alert") { addPriceAlert(cmd.symbol, cmd.op, cmd.price); setMsg(`Alert set: ${cmd.symbol} ${cmd.op} ${cmd.price}`); }
    else { setMsg(cmd.message); return; }
    if (cmd.kind !== "alert") setMsg("");
    setText("");
    ref.current?.blur();
  };

  return (
    <div style={{ display: "flex", alignItems: "center" }}>
      <Input ref={ref} className={s.box} value={text} contentBefore={<Search20Regular />}
        placeholder="Search or command…   Ctrl+K   (AAPL · buffett · AAPL FA · ALERT TSLA < 200)"
        aria-label="Search or command" onChange={(_, d) => setText(d.value)}
        onKeyDown={(e) => { if (e.key === "Enter") run(); if (e.key === "Escape") { setText(""); ref.current?.blur(); } }} />
      {msg && <Text size={200} className={s.msg} role="status">{msg}</Text>}
    </div>
  );
}
```

The classic page doesn't read `?cmd=` today. Add a single line at the end of its `boot()` in `src/howlet/dashboard.html`:
```js
  const qcmd = new URLSearchParams(location.search).get("cmd"); if (qcmd) runCommand(qcmd);
```

- [ ] **Step 10: Wire it into `App.tsx`**

Replace `<TopBar />` with `<TopBar center={<CommandBox />} />` and add `import CommandBox from "./shell/CommandBox";`.

- [ ] **Step 11: Run tests, build, live check, commit**

Run: `npx vitest run`, then `npm run build`. Live at `:8813`: Ctrl+K focuses the box; `AAPL FA` + Enter changes the hash to `#/stock/AAPL/financials`; `news` goes to News; `buffett` opens `/classic` on Buffett's portfolio.

```bash
git add frontend/src src/howlet/static/app src/howlet/dashboard.html
git commit -m "Frontend: Ctrl+K command box with classic command syntax"
```

---

### Task 7: Legacy data adapters (watchlists and Home layout migration)

**Files:**
- Create: `frontend/src/lib/legacy.ts`
- Test: `frontend/src/lib/legacy.test.ts`

**Interfaces:**
- Consumes: `readJson`, `writeJson` (Task 3).
- Produces:
  - `getWatchlists(): Record<string, string[]>`. It reads `howlet_watchlists_v1`, falls back to legacy `howlet_watchlist` as `{default: [...]}`, and finally to the classic default list. It **does not write**, because the classic page owns that migration.
  - `type LegacyWidget = { id: string; type: string; config: Record<string, string>; wide?: boolean; tall?: boolean }`.
  - `type HomeBlock = { i: string; type: string; config: Record<string, string>; x: number; y: number; w: number; h: number }`.
  - `type HomeTab = { id: string; name: string; blocks: HomeBlock[] }`; `type HomeState = { tabs: HomeTab[]; active: string }`; `HOME_KEY = "howlet_home_v1"`.
  - `migrateLayout(legacy: unknown): HomeState | null`. This packs widgets into a 12-column grid: normal widgets are w 6, wide ones w 12, h 8, and tall ones h 16, filled left to right. Unknown shapes return null.
  - `loadHome(firstRun: () => HomeState): HomeState`. Order: `howlet_home_v1` → migrated `howlet_layout_v1` (only if it has at least one widget) → `firstRun()`. It saves the result to `howlet_home_v1`.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/legacy.test.ts`:
```ts
import { getWatchlists, loadHome, migrateLayout, HOME_KEY } from "./legacy";

beforeEach(() => localStorage.clear());

test("watchlists: named store wins, then legacy single list, then defaults", () => {
  localStorage.setItem("howlet_watchlist", JSON.stringify(["IBM"]));
  expect(getWatchlists()).toEqual({ default: ["IBM"] });
  localStorage.setItem("howlet_watchlists_v1", JSON.stringify({ tech: ["NVDA"] }));
  expect(getWatchlists()).toEqual({ tech: ["NVDA"] });
  localStorage.clear();
  expect(getWatchlists().default).toContain("AAPL");
});

test("migrateLayout packs widgets into a 12-col grid", () => {
  const legacy = {
    active: "home",
    tabs: [{ id: "home", name: "HOME", widgets: [
      { id: "a", type: "watchlist", config: { list: "default" } },
      { id: "b", type: "consensus", config: {}, tall: true },
      { id: "c", type: "world-markets", config: {}, wide: true },
    ] }],
  };
  const home = migrateLayout(legacy)!;
  const [a, b, c] = home.tabs[0].blocks;
  expect([a.x, a.y, a.w, a.h]).toEqual([0, 0, 6, 8]);
  expect([b.x, b.y, b.w, b.h]).toEqual([6, 0, 6, 16]);
  expect([c.x, c.w]).toEqual([0, 12]);
  expect(c.y).toBeGreaterThanOrEqual(16);
  expect(a.config).toEqual({ list: "default" });
});

test("migrateLayout rejects junk", () => {
  expect(migrateLayout({ tabs: "x" })).toBeNull();
  expect(migrateLayout(null)).toBeNull();
});

test("loadHome prefers new key, then non-empty legacy, then first run", () => {
  const first = () => ({ tabs: [{ id: "home", name: "Home", blocks: [] }], active: "home" });
  localStorage.setItem("howlet_layout_v1", JSON.stringify({ active: "home", tabs: [{ id: "home", name: "HOME", widgets: [] }] }));
  expect(loadHome(first)).toEqual(first()); // empty legacy -> first run
  expect(JSON.parse(localStorage.getItem(HOME_KEY)!)).toEqual(first());
  localStorage.setItem(HOME_KEY, JSON.stringify({ tabs: [{ id: "t", name: "Mine", blocks: [] }], active: "t" }));
  expect(loadHome(first).active).toBe("t");
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npx vitest run src/lib/legacy`
Expected: FAIL, "Cannot find module './legacy'".

- [ ] **Step 3: Implement `legacy.ts`**

```ts
import { readJson, writeJson } from "./storage";

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const CLASSIC_DEFAULT_WL = ["AAPL", "MSFT", "NVDA", "AMZN", "TSLA", "^GSPC", "BTC-USD"];

export function getWatchlists(): Record<string, string[]> {
  const named = readJson<Record<string, string[]> | null>("howlet_watchlists_v1", null,
    (v): v is Record<string, string[]> => isObj(v));
  if (named && Object.keys(named).length) return named;
  const legacy = readJson<string[]>("howlet_watchlist", [], (v): v is string[] => Array.isArray(v));
  return { default: legacy.length ? legacy : CLASSIC_DEFAULT_WL };
}

export type LegacyWidget = { id: string; type: string; config: Record<string, string>; wide?: boolean; tall?: boolean };
export type HomeBlock = { i: string; type: string; config: Record<string, string>; x: number; y: number; w: number; h: number };
export type HomeTab = { id: string; name: string; blocks: HomeBlock[] };
export type HomeState = { tabs: HomeTab[]; active: string };
export const HOME_KEY = "howlet_home_v1";
const ALWAYS_WIDE = new Set(["world-markets"]); // classic WIDGETS def.wide

export function migrateLayout(legacy: unknown): HomeState | null {
  if (!isObj(legacy) || !Array.isArray(legacy.tabs)) return null;
  const tabs: HomeTab[] = [];
  for (const t of legacy.tabs) {
    if (!isObj(t) || typeof t.id !== "string" || !Array.isArray(t.widgets)) return null;
    const blocks: HomeBlock[] = [];
    let x = 0, y = 0, rowH = 0;
    for (const w of t.widgets as LegacyWidget[]) {
      const width = w.wide || ALWAYS_WIDE.has(w.type) ? 12 : 6;
      const h = w.tall ? 16 : 8;
      if (x + width > 12) { x = 0; y += rowH; rowH = 0; }
      blocks.push({ i: w.id, type: w.type, config: w.config ?? {}, x, y, w: width, h });
      x += width; rowH = Math.max(rowH, h);
    }
    tabs.push({ id: t.id, name: String(t.name ?? t.id), blocks });
  }
  if (!tabs.length) return null;
  const active = typeof legacy.active === "string" && tabs.some((t) => t.id === legacy.active) ? legacy.active : tabs[0].id;
  return { tabs, active };
}

const isHome = (v: unknown): v is HomeState =>
  isObj(v) && Array.isArray(v.tabs) && v.tabs.length > 0 && typeof v.active === "string";

export function loadHome(firstRun: () => HomeState): HomeState {
  const saved = readJson<HomeState | null>(HOME_KEY, null, isHome);
  if (saved) return saved;
  const migrated = migrateLayout(readJson<unknown>("howlet_layout_v1", null, (v): v is unknown => true));
  const result = migrated && migrated.tabs.some((t) => t.blocks.length) ? migrated : firstRun();
  writeJson(HOME_KEY, result);
  return result;
}
```

- [ ] **Step 4: Run the tests**

Run: `npx vitest run src/lib/legacy`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/legacy.ts frontend/src/lib/legacy.test.ts
git commit -m "Frontend: read classic watchlists, migrate classic Home layout"
```

---

### Task 8: Home page grid and the 4 first-run blocks

**Files:**
- Create: `frontend/src/components/Num.tsx`, `frontend/src/blocks/Block.tsx`, `frontend/src/blocks/WatchlistBlock.tsx`, `frontend/src/blocks/SmartMoneyBlock.tsx`, `frontend/src/blocks/PulseBlock.tsx`, `frontend/src/blocks/NewsBlock.tsx`, `frontend/src/blocks/registry.tsx`, `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/App.tsx` (route `home` → `<HomePage/>`), `frontend/src/main.tsx` (grid CSS imports)
- Test: `frontend/src/blocks/registry.test.ts`

**Interfaces:**
- Consumes: `useApi`, `api`, the API types (Task 4); `loadHome`, `HOME_KEY`, `HomeState`, `HomeBlock`, `getWatchlists` (Task 7); `useSettings`, `REFRESH_MS` (Task 3); `useRoute` (Task 5).
- Produces:
  - `Num({ value, pct?, digits?, flash? })`: monospace tabular number, green/red when `pct`, and a short flash on change unless reduced motion.
  - `Block({ title, loading, error, fetchedAt, refreshMs, sec?, onRemove?, children })`: card chrome. A non-SEC error shows "Unavailable, retrying"; an SEC error (`sec`) shows the message. If data is older than `2 * refreshMs` it shows "as of HH:MM".
  - `BLOCKS: Record<string, { label: string; render: (cfg: Record<string,string>) => JSX.Element; defaultSize: {w:number; h:number} }>` for `watchlist`, `manager-changes`, `pulse` and `market-news`.
  - `firstRunHome(): HomeState` with exactly those 4 blocks.
  - `blockFor(type)`: the registry entry, or a fallback that renders "This block arrives in the next update. Open it in the classic view."

- [ ] **Step 1: Write the failing test**

`frontend/src/blocks/registry.test.ts`:
```ts
import { BLOCKS, blockFor, firstRunHome } from "./registry";

test("first run has the 4 calm blocks, no overlaps", () => {
  const home = firstRunHome();
  const blocks = home.tabs[0].blocks;
  expect(blocks.map((b) => b.type).sort()).toEqual(["manager-changes", "market-news", "pulse", "watchlist"]);
  for (const a of blocks) for (const b of blocks) {
    if (a === b) continue;
    const overlap = a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
    expect(overlap).toBe(false);
  }
});

test("every first-run type is registered; unknown types fall back", () => {
  for (const b of firstRunHome().tabs[0].blocks) expect(BLOCKS[b.type]).toBeDefined();
  expect(blockFor("fx-matrix").label).toBe("fx-matrix");
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npx vitest run src/blocks`
Expected: FAIL, "Cannot find module './registry'".

- [ ] **Step 3: Implement `Num.tsx` and `Block.tsx`**

`frontend/src/components/Num.tsx`:
```tsx
import { useEffect, useRef, useState } from "react";

const reduced = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export default function Num({ value, pct, digits = 2, flash = true }: { value: number | null | undefined; pct?: boolean; digits?: number; flash?: boolean }) {
  const prev = useRef(value);
  const [dir, setDir] = useState<"up" | "down" | null>(null);
  useEffect(() => {
    if (flash && !reduced() && prev.current != null && value != null && value !== prev.current) {
      setDir(value > prev.current ? "up" : "down");
      const t = setTimeout(() => setDir(null), 600);
      prev.current = value;
      return () => clearTimeout(t);
    }
    prev.current = value;
  }, [value, flash]);
  if (value == null) return <span style={{ color: "var(--dim)" }}>—</span>;
  const color = pct ? (value > 0 ? "var(--up)" : value < 0 ? "var(--down)" : "var(--dim)") : undefined;
  const text = pct ? `${value > 0 ? "+" : ""}${value.toFixed(digits)}%` : value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return (
    <span style={{ fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color,
      background: dir ? `color-mix(in srgb, var(--${dir}) 25%, transparent)` : undefined,
      transition: "background 0.6s", borderRadius: 3 }}>{text}</span>
  );
}
```

`frontend/src/blocks/Block.tsx`:
```tsx
import { Button, Caption1, Card, CardHeader, Spinner, Text } from "@fluentui/react-components";
import { Dismiss16Regular } from "@fluentui/react-icons";
import type { ReactNode } from "react";

type Props = {
  title: string; loading?: boolean; error?: Error; fetchedAt?: number; refreshMs?: number;
  sec?: boolean; onRemove?: () => void; children?: ReactNode;
};

export default function Block({ title, loading, error, fetchedAt, refreshMs, sec, onRemove, children }: Props) {
  const stale = fetchedAt && refreshMs && Date.now() - fetchedAt > 2 * refreshMs;
  const asOf = fetchedAt ? new Date(fetchedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
  return (
    <Card style={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }} size="small">
      <CardHeader className="drag-handle" style={{ cursor: "grab" }}
        header={<Text weight="semibold">{title}</Text>}
        description={stale || (error && fetchedAt) ? <Caption1>as of {asOf}</Caption1> : undefined}
        action={<span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {loading && <Spinner size="extra-tiny" />}
          {onRemove && <Button appearance="subtle" size="small" icon={<Dismiss16Regular />} aria-label={`Remove ${title}`} onClick={onRemove} />}
        </span>} />
      <div style={{ flex: 1, overflow: "auto" }}>
        {error && !children ? (
          <Caption1 style={{ color: "var(--dim)" }}>{sec ? error.message : "Unavailable, retrying"}</Caption1>
        ) : children}
      </div>
    </Card>
  );
}
```

- [ ] **Step 4: Implement the 4 blocks**

`frontend/src/blocks/WatchlistBlock.tsx`:
```tsx
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import { getWatchlists } from "../lib/legacy";
import { REFRESH_MS, useSettings } from "../lib/settings";
import { useRoute } from "../lib/route";
import Num from "../components/Num";
import Block from "./Block";

export default function WatchlistBlock({ list = "default", onRemove }: { list?: string; onRemove?: () => void }) {
  const refreshMs = REFRESH_MS[useSettings((s) => s.settings.refresh)];
  const symbols = getWatchlists()[list] ?? [];
  const go = useRoute((r) => r.go);
  const { data, error, loading, fetchedAt } = useApi(`wl:${list}:${symbols.join(",")}`, () => api.quotes(symbols), refreshMs);
  return (
    <Block title={`Watchlist · ${list}`} {...{ loading, error, fetchedAt, refreshMs, onRemove }}>
      {data && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <tbody>
            {data.map((q) => (
              <tr key={q.symbol} style={{ cursor: "pointer", borderBottom: "1px solid var(--hair)" }}
                onClick={() => go({ kind: "stock", symbol: q.symbol, tab: "overview" })}>
                <td style={{ padding: "4px 0" }}>{q.symbol}</td>
                <td style={{ textAlign: "right" }}><Num value={q.price} /></td>
                <td style={{ textAlign: "right", width: 72 }}><Num value={q.change_pct} pct /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Block>
  );
}
```

`frontend/src/blocks/SmartMoneyBlock.tsx`:
```tsx
import { Badge } from "@fluentui/react-components";
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import Block from "./Block";

const fmtUsd = (v: number) => `${v < 0 ? "−" : "+"}$${(Math.abs(v) / 1e6).toLocaleString(undefined, { maximumFractionDigits: 0 })}M`;
const COLOR = { NEW: "success", INCREASED: "success", DECREASED: "warning", EXITED: "danger" } as const;

export default function SmartMoneyBlock({ manager = "buffett", onRemove }: { manager?: string; onRemove?: () => void }) {
  // SEC data: immutable per quarter, so refresh hourly at most.
  const { data, error, loading, fetchedAt } = useApi(`diff:${manager}`, () => api.diff(manager), 3_600_000);
  return (
    <Block title={`Smart money · ${manager}`} sec {...{ loading, error, fetchedAt, onRemove }}>
      {data && (
        <>
          <div style={{ color: "var(--dim)", marginBottom: 4 }}>{data.prior_period} → {data.current_period}</div>
          {data.changes.slice(0, 12).map((c) => (
            <div key={c.cusip} style={{ display: "flex", gap: 8, alignItems: "center", padding: "3px 0", borderBottom: "1px solid var(--hair)" }}>
              <Badge size="small" appearance="tint" color={COLOR[c.status as keyof typeof COLOR] ?? "informative"}>{c.status}</Badge>
              <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.issuer}</span>
              <span style={{ fontFamily: "var(--font-mono)" }}>{fmtUsd(c.value_change_usd)}</span>
            </div>
          ))}
        </>
      )}
    </Block>
  );
}
```

Before writing `COLOR`, confirm the status strings with `grep -n "STATUS_ORDER" -A3 src/howlet/diff.py src/howlet/views.py` and use the exact names it shows.

`frontend/src/blocks/PulseBlock.tsx`:
```tsx
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import { REFRESH_MS, useSettings } from "../lib/settings";
import Num from "../components/Num";
import Block from "./Block";

export default function PulseBlock({ onRemove }: { onRemove?: () => void }) {
  const refreshMs = REFRESH_MS[useSettings((s) => s.settings.refresh)];
  const { data, error, loading, fetchedAt } = useApi("tape", api.tape, refreshMs);
  return (
    <Block title="Market pulse" {...{ loading, error, fetchedAt, refreshMs, onRemove }}>
      {data && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 8 }}>
          {data.map((r) => (
            <div key={r.symbol} style={{ background: "var(--elev-1)", borderRadius: 6, padding: "6px 8px" }}>
              <div style={{ color: "var(--dim)", fontSize: "0.85em" }}>{r.label}</div>
              <Num value={r.price} /> <Num value={r.change_pct} pct />
            </div>
          ))}
        </div>
      )}
    </Block>
  );
}
```

`frontend/src/blocks/NewsBlock.tsx`:
```tsx
import { Link } from "@fluentui/react-components";
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import Block from "./Block";

const ago = (iso: string | null) => {
  if (!iso) return "";
  const m = Math.round((Date.now() - Date.parse(iso)) / 60000);
  return m < 60 ? `${m}m` : m < 1440 ? `${Math.round(m / 60)}h` : `${Math.round(m / 1440)}d`;
};

export default function NewsBlock({ onRemove }: { onRemove?: () => void }) {
  const { data, error, loading, fetchedAt } = useApi("news", () => api.news(20), 300_000);
  return (
    <Block title="News" {...{ loading, error, fetchedAt, refreshMs: 300_000, onRemove }}>
      {data?.map((n) => (
        <div key={n.link} style={{ padding: "4px 0", borderBottom: "1px solid var(--hair)" }}>
          <Link href={n.link} target="_blank" rel="noreferrer">{n.title}</Link>
          <div style={{ color: "var(--dim)", fontSize: "0.85em" }}>{n.source} · {ago(n.published)}</div>
        </div>
      ))}
    </Block>
  );
}
```

- [ ] **Step 5: Implement `registry.tsx`**

```tsx
import type { JSX } from "react";
import { Body1, Link } from "@fluentui/react-components";
import type { HomeState } from "../lib/legacy";
import Block from "./Block";
import WatchlistBlock from "./WatchlistBlock";
import SmartMoneyBlock from "./SmartMoneyBlock";
import PulseBlock from "./PulseBlock";
import NewsBlock from "./NewsBlock";

type Entry = { label: string; defaultSize: { w: number; h: number }; render: (cfg: Record<string, string>, onRemove: () => void) => JSX.Element };

export const BLOCKS: Record<string, Entry> = {
  watchlist: { label: "Watchlist", defaultSize: { w: 5, h: 10 }, render: (c, r) => <WatchlistBlock list={c.list} onRemove={r} /> },
  "manager-changes": { label: "Smart money moves", defaultSize: { w: 7, h: 10 }, render: (c, r) => <SmartMoneyBlock manager={c.manager} onRemove={r} /> },
  pulse: { label: "Market pulse", defaultSize: { w: 12, h: 5 }, render: (_c, r) => <PulseBlock onRemove={r} /> },
  "market-news": { label: "News", defaultSize: { w: 12, h: 10 }, render: (_c, r) => <NewsBlock onRemove={r} /> },
};

export function blockFor(type: string): Entry {
  return BLOCKS[type] ?? {
    label: type, defaultSize: { w: 6, h: 8 },
    render: (_c, r) => (
      <Block title={type} onRemove={r}>
        <Body1>This block arrives in the next update. Open it in the <Link href="/classic">classic view</Link>.</Body1>
      </Block>
    ),
  };
}

export function firstRunHome(): HomeState {
  return {
    active: "home",
    tabs: [{
      id: "home", name: "Home", blocks: [
        { i: "pulse", type: "pulse", config: {}, x: 0, y: 0, w: 12, h: 5 },
        { i: "wl", type: "watchlist", config: { list: "default" }, x: 0, y: 5, w: 5, h: 10 },
        { i: "sm", type: "manager-changes", config: { manager: "buffett" }, x: 5, y: 5, w: 7, h: 10 },
        { i: "news", type: "market-news", config: {}, x: 0, y: 15, w: 12, h: 10 },
      ],
    }],
  };
}
```

- [ ] **Step 6: Run the registry test**

Run: `npx vitest run src/blocks`
Expected: 2 passed.

- [ ] **Step 7: Implement `HomePage.tsx`**

```tsx
import { Button, Menu, MenuItem, MenuList, MenuPopover, MenuTrigger, Tab, TabList } from "@fluentui/react-components";
import { Add16Regular } from "@fluentui/react-icons";
import { useState } from "react";
import { Responsive, WidthProvider, type Layout } from "react-grid-layout";
import { HOME_KEY, loadHome, type HomeState } from "../lib/legacy";
import { writeJson } from "../lib/storage";
import { BLOCKS, blockFor, firstRunHome } from "../blocks/registry";

const Grid = WidthProvider(Responsive);

export default function HomePage() {
  const [home, setHome] = useState<HomeState>(() => loadHome(firstRunHome));
  const save = (h: HomeState) => { setHome(h); writeJson(HOME_KEY, h); };
  const tab = home.tabs.find((t) => t.id === home.active) ?? home.tabs[0];

  const onLayout = (layout: Layout[]) => {
    const pos = new Map(layout.map((l) => [l.i, l]));
    save({ ...home, tabs: home.tabs.map((t) => t.id !== tab.id ? t : {
      ...t, blocks: t.blocks.map((b) => { const l = pos.get(b.i); return l ? { ...b, x: l.x, y: l.y, w: l.w, h: l.h } : b; }),
    }) });
  };
  const addBlock = (type: string) => {
    const { w, h } = BLOCKS[type].defaultSize;
    const cfg: Record<string, string> = type === "watchlist" ? { list: "default" } : type === "manager-changes" ? { manager: "buffett" } : {};
    const block = { i: `${type}-${Date.now().toString(36)}`, type, config: cfg, x: 0, y: Infinity, w, h };
    save({ ...home, tabs: home.tabs.map((t) => t.id === tab.id ? { ...t, blocks: [...t.blocks, block] } : t) });
  };
  const removeBlock = (i: string) =>
    save({ ...home, tabs: home.tabs.map((t) => t.id === tab.id ? { ...t, blocks: t.blocks.filter((b) => b.i !== i) } : t) });

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <TabList selectedValue={tab.id} onTabSelect={(_, d) => save({ ...home, active: String(d.value) })}>
          {home.tabs.map((t) => <Tab key={t.id} value={t.id}>{t.name}</Tab>)}
        </TabList>
        <Menu>
          <MenuTrigger disableButtonEnhancement><Button icon={<Add16Regular />} appearance="subtle">Add block</Button></MenuTrigger>
          <MenuPopover><MenuList>
            {Object.entries(BLOCKS).map(([type, e]) => <MenuItem key={type} onClick={() => addBlock(type)}>{e.label}</MenuItem>)}
          </MenuList></MenuPopover>
        </Menu>
      </div>
      <Grid className="layout" rowHeight={28} margin={[10, 10]} draggableHandle=".drag-handle"
        breakpoints={{ lg: 0 }} cols={{ lg: 12 }}
        layouts={{ lg: tab.blocks.map(({ i, x, y, w, h }) => ({ i, x, y, w, h, minW: 3, minH: 4 })) }}
        onLayoutChange={onLayout}>
        {tab.blocks.map((b) => <div key={b.i}>{blockFor(b.type).render(b.config, () => removeBlock(b.i))}</div>)}
      </Grid>
    </div>
  );
}
```

Tab create, rename and delete, plus named layout snapshots, are in plan 2. This task only switches between migrated tabs.

- [ ] **Step 8: Grid CSS and routing**

In `frontend/src/main.tsx` add at the top:
```ts
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
```
(`react-resizable` is installed as a dependency of `react-grid-layout`.)

In `App.tsx` add `import HomePage from "./pages/HomePage";` and change the page selection to:
```tsx
  const page = route.kind === "stock"
    ? <PlaceholderPage title={route.symbol} />
    : route.page === "home" ? <HomePage /> : <PlaceholderPage title={PAGE_META[route.page].label} />;
```

- [ ] **Step 9: Test, build and check live**

Run: `npx vitest run`, then `npm run build`. Live at `:8813` with a fresh profile (DevTools → Application → clear `howlet_home_v1` only):
- With an empty classic layout you get the 4 blocks, filled with real data.
- Drag a block by its header, then resize from the corner. Reload, and the positions persist.
- A classic layout with widgets migrates into the tabs. Unported blocks show the "next update" card.
- In DevTools Network, block one request (for example `/api/news`). Only the News block shows "Unavailable, retrying".

- [ ] **Step 10: Commit**

```bash
git add frontend/src src/howlet/static/app
git commit -m "Frontend: Home grid with drag/resize and four first-run blocks"
```

---

### Task 9: Stock page Overview with 🦉 chips

**Files:**
- Create: `frontend/src/components/OwlChips.tsx`, `frontend/src/pages/StockPage.tsx`
- Modify: `frontend/src/App.tsx` (stock route → `<StockPage/>`)
- Test: `frontend/src/components/OwlChips.test.tsx`

**Interfaces:**
- Consumes: `api.security`, `api.holders`, `HoldersResult` (Task 4); `useApi` (Task 4); `useRoute`, `StockTab` (Task 5); `useSettings` (Task 3); `Num` (Task 8).
- Produces: `OwlChips({ symbol })` renders nothing on error or empty data, and otherwise one chip per holder ("🦉 buffett · 21.4%"), sorted by weight. `StockPage({ symbol, tab })` shows tabs Overview / Chart / Financials / Holders / News / Options (Options only if `showOptions`). Only Overview is real here; the other tabs render `PlaceholderPage`.

The spec also asks for last-quarter action on the chips (new / added / trimmed / exited). `/api/holders` doesn't return it, and adding it is a backend change, so it's **in plan 2**. Here the chips show holding and weight.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/OwlChips.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import OwlChips from "./OwlChips";

afterEach(() => vi.restoreAllMocks());
const reply = (body: unknown, status = 200) =>
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(body), { status }));

test("one chip per holder, heaviest first", async () => {
  reply({ symbol: "AAPL", tracked_managers: ["buffett", "lilu"], holders: [
    { manager: "lilu", weight_pct: 5.1, value_usd: 1, shares: 1, issuer: "APPLE", period_of_report: null },
    { manager: "buffett", weight_pct: 21.43, value_usd: 2, shares: 2, issuer: "APPLE", period_of_report: null },
  ] });
  render(<OwlChips symbol="AAPL" />);
  await waitFor(() => expect(screen.getAllByText(/🦉/)).toHaveLength(2));
  expect(screen.getAllByText(/🦉/)[0].textContent).toContain("buffett · 21.4%");
});

test("renders nothing when the call fails (decoration only)", async () => {
  reply({ error: "boom" }, 502);
  const { container } = render(<OwlChips symbol="AAPL" />);
  await new Promise((r) => setTimeout(r, 20));
  expect(container.textContent).toBe("");
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npx vitest run src/components`
Expected: FAIL, "Cannot find module './OwlChips'".

- [ ] **Step 3: Implement `OwlChips.tsx`**

```tsx
import { Tag, TagGroup, Tooltip } from "@fluentui/react-components";
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";

export default function OwlChips({ symbol }: { symbol: string }) {
  // Holders come from SEC 13Fs, which are immutable per quarter: no refresh timer.
  const { data, error } = useApi(`holders:${symbol}`, () => api.holders(symbol));
  if (error || !data || !data.holders.length) return null;
  const holders = [...data.holders].sort((a, b) => b.weight_pct - a.weight_pct);
  return (
    <TagGroup aria-label="Tracked superinvestors holding this stock" style={{ flexWrap: "wrap", gap: 4 }}>
      {holders.map((h) => (
        <Tooltip key={h.manager + h.issuer} relationship="description"
          content={`${h.shares.toLocaleString()} shares · $${(h.value_usd / 1e6).toFixed(0)}M · period ${h.period_of_report ?? "?"}`}>
          <Tag size="small" appearance="brand">🦉 {h.manager} · {h.weight_pct.toFixed(1)}%</Tag>
        </Tooltip>
      ))}
    </TagGroup>
  );
}
```

- [ ] **Step 4: Run the test**

Run: `npx vitest run src/components`
Expected: 2 passed.

- [ ] **Step 5: Implement `StockPage.tsx`**

```tsx
import { Body1, Card, Tab, TabList, Title2 } from "@fluentui/react-components";
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import { useRoute, type StockTab } from "../lib/route";
import { REFRESH_MS, useSettings } from "../lib/settings";
import Num from "../components/Num";
import OwlChips from "../components/OwlChips";
import PlaceholderPage from "./PlaceholderPage";

const TABS: [StockTab, string][] = [["overview", "Overview"], ["chart", "Chart"], ["financials", "Financials"], ["holders", "Holders"], ["news", "News"], ["options", "Options"]];

export default function StockPage({ symbol, tab }: { symbol: string; tab: StockTab }) {
  const { showOptions, refresh } = useSettings((s) => s.settings);
  const go = useRoute((r) => r.go);
  const { data: q, error } = useApi(`sec:${symbol}`, () => api.security(symbol), REFRESH_MS[refresh]);
  const tabs = TABS.filter(([t]) => t !== "options" || showOptions);

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <Title2>{symbol}</Title2>
        {q && <Body1 style={{ color: "var(--dim)" }}>{q.long_name ?? q.name}</Body1>}
        {q && <span style={{ fontSize: "1.6em" }}><Num value={q.price} /></span>}
        {q && <Num value={q.change_pct} pct />}
        {error && !q && <Body1 style={{ color: "var(--dim)" }}>Quote unavailable</Body1>}
      </div>
      <OwlChips symbol={symbol} />
      <TabList selectedValue={tab} onTabSelect={(_, d) => go({ kind: "stock", symbol, tab: d.value as StockTab })}>
        {tabs.map(([t, label]) => <Tab key={t} value={t}>{label}</Tab>)}
      </TabList>
      {tab === "overview" && q ? (
        <Card style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
          {([
            ["Previous close", q.previous_close], ["Day low", q.day_low], ["Day high", q.day_high],
            ["52-week low", q.week52_low], ["52-week high", q.week52_high], ["Volume", q.volume],
          ] as [string, number | null][]).map(([k, v]) => (
            <div key={k}><div style={{ color: "var(--dim)" }}>{k}</div><Num value={v} digits={k === "Volume" ? 0 : 2} flash={false} /></div>
          ))}
        </Card>
      ) : tab !== "overview" ? (
        <PlaceholderPage title={TABS.find(([t]) => t === tab)?.[1] ?? tab} />
      ) : null}
    </div>
  );
}
```

Before writing this, check the field names `/api/security/<symbol>` really returns: run `curl -s localhost:8813/api/security/AAPL | python -c "import json,sys; print(sorted(json.load(sys.stdin)))"` with the dashboard running. Adjust `Security` in `api.ts` if any key differs (for example `long_name` vs `name`).

- [ ] **Step 6: Route it, then test, build and check live**

In `App.tsx` add `import StockPage from "./pages/StockPage";` and replace the stock branch with `<StockPage symbol={route.symbol} tab={route.tab} />`.

Run: `npx vitest run`, then `npm run build`. Live: Ctrl+K `AAPL` shows the price, stats and 🦉 chips; compare them with `/classic` `AAPL HDS`, which should list the same managers. `BRK-B` should show a buffett chip. `^GSPC` shows no chips and no error.

- [ ] **Step 7: Commit**

```bash
git add frontend/src src/howlet/static/app
git commit -m "Frontend: stock page overview with superinvestor owl chips"
```

---

### Task 10: Alerts bell (price + 13F filing alerts)

**Files:**
- Create: `frontend/src/shell/AlertsBell.tsx`
- Modify: `frontend/src/App.tsx` (pass `<AlertsBell/>` as `TopBar right`), `frontend/src/lib/api.ts` (add `filingAlerts`)
- Test: covered by `alerts.test.ts` (Task 6) plus the live check; the bell is UI wiring over that tested logic.

**Interfaces:**
- Consumes: `getAlerts`, `saveAlerts`, `removeAlert`, `evaluate`, `PriceAlert` (Task 6); `readJson`, `writeJson` (Task 3); `api.quotes` (Task 4); `useSettings` (`alertSound`); `useRoute` (Task 5).
- Produces:
  - `api.filingAlerts()`: `GET /api/filing-alerts` returning `{label: string; cik: string; accession_number: string; filing_date: string; period_of_report: string | null}[]`.

- [ ] **Step 1: Add `filingAlerts` to `api.ts`**

```ts
export type FilingAlert = { label: string; cik: string; accession_number: string; filing_date: string; period_of_report: string | null };
// inside the api object:
  filingAlerts: () => getJson<FilingAlert[]>("/api/filing-alerts"),
```

- [ ] **Step 2: Implement `AlertsBell.tsx` and wire it**

This mirrors the classic bell's behaviour: price alerts poll every 60 seconds, filing alerts every 30 minutes, the first filing poll baselines silently into `howlet_seen_filings_v1`, Windows notifications go out when permitted, and MARK ALL SEEN clears fired price alerts and records the seen accession numbers.

```tsx
import { Button, CounterBadge, Popover, PopoverSurface, PopoverTrigger, Text, Link } from "@fluentui/react-components";
import { Alert24Regular, Dismiss16Regular } from "@fluentui/react-icons";
import { useCallback, useEffect, useState } from "react";
import { evaluate, getAlerts, removeAlert, saveAlerts, type PriceAlert } from "../lib/alerts";
import { api, type FilingAlert } from "../lib/api";
import { readJson, writeJson } from "../lib/storage";
import { useSettings } from "../lib/settings";
import { useRoute } from "../lib/route";

const SEEN_KEY = "howlet_seen_filings_v1"; // shared with the classic page
const chime = () => {
  try { // 150 ms 880 Hz tone: no audio asset to ship
    const ctx = new AudioContext(), osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.frequency.value = 880; gain.gain.value = 0.05;
    osc.connect(gain); gain.connect(ctx.destination);
    osc.start(); osc.stop(ctx.currentTime + 0.15);
  } catch { /* audio blocked: the notification still shows */ }
};
const notify = (title: string, body: string) => {
  if ("Notification" in window && Notification.permission === "granted") new Notification(title, { body });
};

export default function AlertsBell() {
  const [alerts, setAlerts] = useState<PriceAlert[]>(getAlerts);
  const [newFilings, setNewFilings] = useState<FilingAlert[]>([]);
  const sound = useSettings((s) => s.settings.alertSound);
  const go = useRoute((r) => r.go);

  const pollPrices = useCallback(async () => {
    const current = getAlerts();
    const syms = [...new Set(current.filter((a) => !a.fired).map((a) => a.sym))];
    if (!syms.length) { setAlerts(current); return; }
    try {
      const rows = await api.quotes(syms);
      const prices = Object.fromEntries(rows.map((r) => [r.symbol.toUpperCase(), r.price]));
      const fired = evaluate(current, prices, new Date().toISOString());
      if (fired.length) {
        const byId = new Map(fired.map((f) => [f.id, f]));
        // Re-read so an alert added during the fetch is kept.
        saveAlerts(getAlerts().map((a) => byId.get(a.id) ?? a));
        fired.forEach((f) => notify(`${f.sym} ${f.op} ${f.px}`, `${f.sym} is at ${f.fired!.price.toFixed(2)}`));
        if (sound) chime();
      }
    } catch { /* market data is decoration: try again next tick */ }
    setAlerts(getAlerts());
  }, [sound]);

  const pollFilings = useCallback(async () => {
    let rows: FilingAlert[];
    try { rows = await api.filingAlerts(); } catch { return; }
    const seen = readJson<Record<string, string>>(SEEN_KEY, {}, (v): v is Record<string, string> => !!v && typeof v === "object" && !Array.isArray(v));
    if (!Object.keys(seen).length) {
      rows.forEach((r) => { seen[r.cik] = r.accession_number; });
      writeJson(SEEN_KEY, seen); // first run: baseline silently
      return;
    }
    const fresh = rows.filter((r) => seen[r.cik] && seen[r.cik] !== r.accession_number);
    fresh.forEach((f) => notify(`New 13F filing: ${f.label.toUpperCase()}`, `Filed ${f.filing_date}`));
    setNewFilings(fresh);
  }, []);

  useEffect(() => {
    pollPrices(); pollFilings();
    const a = setInterval(pollPrices, 60_000), b = setInterval(pollFilings, 1_800_000);
    return () => { clearInterval(a); clearInterval(b); };
  }, [pollPrices, pollFilings]);

  const markSeen = () => {
    const seen = readJson<Record<string, string>>(SEEN_KEY, {}, (v): v is Record<string, string> => !!v && typeof v === "object");
    newFilings.forEach((f) => { seen[f.cik] = f.accession_number; });
    writeJson(SEEN_KEY, seen);
    saveAlerts(getAlerts().filter((a) => !a.fired));
    setNewFilings([]); setAlerts(getAlerts());
  };

  const count = alerts.filter((a) => a.fired).length + newFilings.length;
  return (
    <Popover onOpenChange={(_, d) => { if (d.open && "Notification" in window && Notification.permission === "default") Notification.requestPermission(); }}>
      <PopoverTrigger disableButtonEnhancement>
        <Button appearance="subtle" aria-label={`Alerts, ${count} new`} icon={
          <span style={{ position: "relative" }}><Alert24Regular />
            {count > 0 && <CounterBadge count={count} size="small" color="danger" style={{ position: "absolute", top: -6, right: -8 }} />}</span>} />
      </PopoverTrigger>
      <PopoverSurface style={{ width: 340 }}>
        <Text weight="semibold">Price alerts</Text>
        <Text block size={200} style={{ color: "var(--dim)" }}>Add with Ctrl+K: ALERT AAPL &gt; 350. Checked every minute while Howlet is open.</Text>
        {alerts.length === 0 && <Text block size={200}>None set.</Text>}
        {alerts.map((a) => (
          <div key={a.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "2px 0" }}>
            <Link onClick={() => go({ kind: "stock", symbol: a.sym, tab: "overview" })}>{a.sym}</Link>
            <span style={{ fontFamily: "var(--font-mono)" }}>{a.op} {a.px.toFixed(2)}</span>
            {a.fired ? <span style={{ color: "var(--up)" }}>hit {a.fired.price.toFixed(2)}</span> : <span style={{ color: "var(--dim)" }}>watching</span>}
            <Button size="small" appearance="subtle" icon={<Dismiss16Regular />} aria-label={`Remove ${a.sym} alert`}
              style={{ marginLeft: "auto" }} onClick={() => { removeAlert(a.id); setAlerts(getAlerts()); }} />
          </div>
        ))}
        <Text block weight="semibold" style={{ marginTop: 10 }}>New 13F filings</Text>
        {newFilings.length === 0
          ? <Text block size={200} style={{ color: "var(--dim)" }}>None since you last looked. Checked every 30 minutes.</Text>
          : newFilings.map((f) => <Text block key={f.accession_number}>{f.label.toUpperCase()} · filed {f.filing_date}</Text>)}
        {count > 0 && <Button size="small" style={{ marginTop: 10 }} onClick={markSeen}>Mark all seen</Button>}
      </PopoverSurface>
    </Popover>
  );
}
```

In `App.tsx`: `import AlertsBell from "./shell/AlertsBell";` and `<TopBar center={<CommandBox />} right={<AlertsBell />} />`.

- [ ] **Step 3: Test, build and check live**

Run: `npx vitest run`, then `npm run build`. Live: Ctrl+K `ALERT AAPL > 1` fires within 60 seconds, the chime plays and the badge shows 1. Open `/classic` and its bell shows the same alert, because the key is shared. Mark all seen clears it. Removing an alert with × works.

- [ ] **Step 4: Commit**

```bash
git add frontend/src src/howlet/static/app
git commit -m "Frontend: alerts bell sharing price/filing alerts with classic"
```

---

### Task 11: Settings page

**Files:**
- Create: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/App.tsx` (route `settings` → `<SettingsPage/>`)
- Test: `frontend/src/pages/SettingsPage.test.tsx`

**Interfaces:**
- Consumes: `useSettings`, `PAGE_IDS`, `DEFAULT_SETTINGS`, `Settings` (Task 3); `ACCENT_SWATCHES` (Task 2); `PAGE_META` (Task 5); `HOME_KEY` (Task 7); `firstRunHome` (Task 8).
- Produces: a Settings page with four sections. **Appearance:** theme mode, accent swatches plus a custom colour, density, text size. **Rail:** per page, a visibility switch and up/down buttons; Home and Settings switches are disabled. **Defaults:** start page, chart range, refresh speed, alert sound, show Options. **Layouts:** Restore default Home layout, plus Export and Import of every `howlet_*` key as JSON. **Keyboard shortcuts:** a read-only list.

Tracked managers (custom CIKs) need the backend to accept a manager list, so they're **in plan 2**. Chart range and indicators are stored now and used by the Chart tab in plan 2.

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/SettingsPage.test.tsx`:
```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import SettingsPage from "./SettingsPage";
import { useSettings, DEFAULT_SETTINGS } from "../lib/settings";

beforeEach(() => { localStorage.clear(); useSettings.setState({ settings: DEFAULT_SETTINGS }); });
const ui = () => render(<FluentProvider theme={webDarkTheme}><SettingsPage /></FluentProvider>);

test("theme mode radio updates the store", () => {
  ui();
  fireEvent.click(screen.getByLabelText("Dark"));
  expect(useSettings.getState().settings.themeMode).toBe("dark");
});

test("hiding a rail page updates railHidden; Home cannot be hidden", () => {
  ui();
  fireEvent.click(screen.getByRole("switch", { name: "Show News" }));
  expect(useSettings.getState().settings.railHidden).toContain("news");
  expect(screen.getByRole("switch", { name: "Show Home" })).toBeDisabled();
});

test("moving a page up reorders the rail", () => {
  ui();
  fireEvent.click(screen.getByRole("button", { name: "Move Markets up" }));
  expect(useSettings.getState().settings.railOrder.slice(0, 2)).toEqual(["markets", "home"]);
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npx vitest run src/pages`
Expected: FAIL, "Cannot find module './SettingsPage'".

- [ ] **Step 3: Implement `SettingsPage.tsx`**

```tsx
import {
  Button, Card, Dropdown, Field, Option, Radio, RadioGroup, Switch, Text, Title3, Subtitle2,
} from "@fluentui/react-components";
import { ArrowUp16Regular, ArrowDown16Regular } from "@fluentui/react-icons";
import { useRef, useState } from "react";
import { useSettings, PAGE_IDS, type PageId, type Settings } from "../lib/settings";
import { PAGE_META } from "../shell/Rail";
import { HOME_KEY } from "../lib/legacy";
import { writeJson } from "../lib/storage";
import { firstRunHome } from "../blocks/registry";
import { ACCENT_SWATCHES } from "../theme/tokens";

const RANGES = ["1mo", "3mo", "6mo", "1y", "5y"];
const SHORTCUTS: [string, string][] = [["Ctrl+K", "Search or command"], ["Ctrl+1 … Ctrl+7", "Jump to rail page"], ["Esc", "Close / clear"], ["Alt+←", "Back"]];

export default function SettingsPage() {
  const { settings: s, update } = useSettings();
  const [msg, setMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const set = <K extends keyof Settings>(k: K) => (v: Settings[K]) => update({ [k]: v } as Partial<Settings>);

  const move = (p: PageId, dir: -1 | 1) => {
    const order = [...s.railOrder];
    const i = order.indexOf(p), j = i + dir;
    if (j < 0 || j >= order.length) return;
    [order[i], order[j]] = [order[j], order[i]];
    update({ railOrder: order });
  };

  const exportState = () => {
    const data: Record<string, string> = {};
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)!;
      if (k.startsWith("howlet_")) data[k] = localStorage.getItem(k)!;
    }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    a.download = `howlet-backup-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
  };
  const importState = async (f: File) => {
    try {
      const data = JSON.parse(await f.text());
      if (!data || typeof data !== "object") throw new Error("not an object");
      let n = 0;
      for (const [k, v] of Object.entries(data)) if (k.startsWith("howlet_") && typeof v === "string") { localStorage.setItem(k, v); n++; }
      setMsg(`Imported ${n} items. Reloading…`);
      setTimeout(() => location.reload(), 600);
    } catch { setMsg("That file isn't a Howlet backup."); }
  };

  return (
    <div style={{ padding: 16, display: "grid", gap: 12, maxWidth: 760 }}>
      <Title3>Settings</Title3>

      <Card><Subtitle2>Appearance</Subtitle2>
        <Field label="Theme"><RadioGroup layout="horizontal" value={s.themeMode} onChange={(_, d) => set("themeMode")(d.value as Settings["themeMode"])}>
          <Radio value="system" label="Follow Windows" /><Radio value="light" label="Light" /><Radio value="dark" label="Dark" />
        </RadioGroup></Field>
        <Field label="Accent colour"><div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {ACCENT_SWATCHES.map((c) => (
            <button key={c} aria-label={`Accent ${c}`} aria-pressed={s.accent === c} onClick={() => set("accent")(c)}
              style={{ width: 24, height: 24, borderRadius: 12, background: c, cursor: "pointer",
                border: s.accent === c ? "2px solid var(--text)" : "2px solid transparent" }} />
          ))}
          <input type="color" aria-label="Custom accent colour" value={s.accent} onChange={(e) => set("accent")(e.target.value)} />
        </div></Field>
        <Field label="Density"><RadioGroup layout="horizontal" value={s.density} onChange={(_, d) => set("density")(d.value as Settings["density"])}>
          <Radio value="comfortable" label="Comfortable" /><Radio value="compact" label="Compact" />
        </RadioGroup></Field>
        <Field label="Text size"><RadioGroup layout="horizontal" value={s.textSize} onChange={(_, d) => set("textSize")(d.value as Settings["textSize"])}>
          <Radio value="small" label="Small" /><Radio value="medium" label="Medium" /><Radio value="large" label="Large" />
        </RadioGroup></Field>
      </Card>

      <Card><Subtitle2>Rail</Subtitle2>
        {s.railOrder.map((p, i) => {
          const locked = p === "home" || p === "settings";
          return (
            <div key={p} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {PAGE_META[p].icon}<Text style={{ flex: 1 }}>{PAGE_META[p].label}</Text>
              <Button size="small" appearance="subtle" icon={<ArrowUp16Regular />} aria-label={`Move ${PAGE_META[p].label} up`} disabled={i === 0} onClick={() => move(p, -1)} />
              <Button size="small" appearance="subtle" icon={<ArrowDown16Regular />} aria-label={`Move ${PAGE_META[p].label} down`} disabled={i === s.railOrder.length - 1} onClick={() => move(p, 1)} />
              <Switch aria-label={`Show ${PAGE_META[p].label}`} checked={!s.railHidden.includes(p)} disabled={locked}
                onChange={(_, d) => update({ railHidden: d.checked ? s.railHidden.filter((x) => x !== p) : [...s.railHidden, p] })} />
            </div>
          );
        })}
      </Card>

      <Card><Subtitle2>Defaults</Subtitle2>
        <Field label="Start page"><Dropdown value={PAGE_META[s.startPage].label} selectedOptions={[s.startPage]}
          onOptionSelect={(_, d) => set("startPage")(d.optionValue as PageId)}>
          {PAGE_IDS.map((p) => <Option key={p} value={p}>{PAGE_META[p].label}</Option>)}
        </Dropdown></Field>
        <Field label="Default chart range"><Dropdown value={s.chartRange} selectedOptions={[s.chartRange]} onOptionSelect={(_, d) => set("chartRange")(d.optionValue!)}>
          {RANGES.map((r) => <Option key={r} value={r}>{r}</Option>)}
        </Dropdown></Field>
        <Field label="Refresh speed (prices, news, crypto)"><RadioGroup layout="horizontal" value={s.refresh} onChange={(_, d) => set("refresh")(d.value as Settings["refresh"])}>
          <Radio value="fast" label="Fast (15s)" /><Radio value="normal" label="Normal (1 min)" /><Radio value="slow" label="Slow (5 min)" />
        </RadioGroup></Field>
        <Switch label="Alert sound" checked={s.alertSound} onChange={(_, d) => set("alertSound")(d.checked)} />
        <Switch label="Show Options tab (experimental)" checked={s.showOptions} onChange={(_, d) => set("showOptions")(d.checked)} />
      </Card>

      <Card><Subtitle2>Layouts &amp; backup</Subtitle2>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Button onClick={() => { writeJson(HOME_KEY, firstRunHome()); setMsg("Home reset to the default 4 blocks."); }}>Restore default Home</Button>
          <Button onClick={exportState}>Export backup</Button>
          <Button onClick={() => fileRef.current?.click()}>Import backup</Button>
          <input ref={fileRef} type="file" accept="application/json" hidden onChange={(e) => e.target.files?.[0] && importState(e.target.files[0])} />
        </div>
        {msg && <Text role="status">{msg}</Text>}
      </Card>

      <Card><Subtitle2>Keyboard shortcuts</Subtitle2>
        {SHORTCUTS.map(([k, v]) => <div key={k} style={{ display: "flex", gap: 12 }}><code style={{ minWidth: 140 }}>{k}</code><Text>{v}</Text></div>)}
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: Density CSS**

Add `frontend/src/index.css`, imported in `main.tsx`:
```css
body { margin: 0; background: var(--bg); color: var(--text); font-family: var(--font-text); }
[data-density="compact"] .fui-Card { padding: 6px; gap: 4px; }
[data-density="compact"] td { padding-top: 1px !important; padding-bottom: 1px !important; }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
```

- [ ] **Step 5: Route it, then test and build**

In `App.tsx`: `import SettingsPage from "./pages/SettingsPage";` and render `<SettingsPage />` when `route.page === "settings"`.

Run: `npx vitest run`, then `npm run build`
Expected: all tests pass and the build succeeds.

- [ ] **Step 6: Live check**

At `:8813`:
- Switch theme Dark → Light → Follow Windows. Pick each accent and a custom colour; the rail highlight and links change.
- Set Compact, then Large text.
- Hide News: it leaves the rail, and Ctrl+number follows the new order.
- Export a backup, change something, import the backup: state is restored.
- Verify fonts with a computed-style probe (CLAUDE.md gotcha: you can't grep for a missing declaration). In the browser console, run `[...document.querySelectorAll('input,button,td,span')].map(e => getComputedStyle(e).fontFamily).filter(f => !/Segoe|Cascadia|Consolas/.test(f))`. It should print `[]`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src src/howlet/static/app
git commit -m "Frontend: settings page (appearance, rail, defaults, backup)"
```

---

### Task 12: Error boundary, bundle check, docs and the shell checkpoint

**Files:**
- Modify: `frontend/src/main.tsx` (error boundary), `CLAUDE.md` (module map + Status + gotcha), `README.md` (one "Frontend development" paragraph)

**Interfaces:**
- Produces: a top-level error boundary with a "Reset settings" button that removes **only** `howlet_settings_v1` and `howlet_home_v1`.

- [ ] **Step 1: Add the error boundary in `main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import "./index.css";
import App from "./App";

class Boundary extends React.Component<{ children: React.ReactNode }, { err: Error | null }> {
  state = { err: null as Error | null };
  static getDerivedStateFromError(err: Error) { return { err }; }
  render() {
    if (!this.state.err) return this.props.children;
    return (
      <div style={{ padding: 24, fontFamily: "Segoe UI, sans-serif" }}>
        <h2>Howlet hit an error</h2>
        <pre style={{ whiteSpace: "pre-wrap" }}>{this.state.err.message}</pre>
        <p>Your watchlists, alerts and portfolio are untouched. Resetting only clears display settings and the Home layout.</p>
        <button onClick={() => { localStorage.removeItem("howlet_settings_v1"); localStorage.removeItem("howlet_home_v1"); location.reload(); }}>Reset settings</button>
        {" "}<a href="/classic">Open classic view</a>
      </div>
    );
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><Boundary><App /></Boundary></React.StrictMode>,
);
```

(This uses plain HTML on purpose: the boundary must render even if Fluent itself is what failed.)

- [ ] **Step 2: Full test run and production build**

Run: `npx vitest run`, then `npm run build`, then (repo root) `PYTHONPATH=src pytest tests/ -q` and `ruff check src/ tests/`
Expected: all green. Write down the gzipped JS size that Vite prints. The spec expects roughly 300–500 KB. If it's over 700 KB, note it in the checkpoint report (don't optimise now).

- [ ] **Step 3: Full live pass at `http://localhost:8813/`**

Check each item and note the result:
1. First load follows the Windows theme; the rail shows 7 pages.
2. Home shows 4 blocks with live data; drag and resize persist across reload.
3. Ctrl+K `AAPL` shows the stock page with 🦉 chips. Ctrl+K `buffett` opens classic PORT.
4. `ALERT AAPL > 1` fires; the bell badge appears; `/classic` sees the same alert.
5. In Settings, every control changes the UI live and survives a reload.
6. Block `/api/tape` in DevTools: only Market pulse degrades.
7. `/classic` still works fully.
8. Read the console: no errors.

- [ ] **Step 4: Update docs**

In `CLAUDE.md`:
- In the module map, add a row: "`frontend/` | React + Fluent UI v9 app (Vite), builds into `static/app/`; served at `/`. Old UI at `/classic` until plan 2 completes".
- Under Status, add one dated line: "React shell live at `/` (rail, Ctrl+K, settings, Home grid, stock overview + 🦉 chips, alerts bell); other pages still in `/classic`".
- Add this gotcha: "**Vite dev server (5173) is a different origin → separate localStorage.** Your real watchlists/alerts only appear at `:8813`; always verify there."

In `README.md`, add a short "Frontend development" section with `cd frontend && npm install && npm run dev`, `npm test`, and `npm run build`. Note that the built files are committed and Node is not needed to run Howlet.

- [ ] **Step 5: Commit**

```bash
git add frontend/src src/howlet/static/app CLAUDE.md README.md
git commit -m "Frontend: error boundary, docs; React shell complete"
```

- [ ] **Step 6: CHECKPOINT: stop and show Vineeth**

Report the live-pass results, the bundle size, and screenshots of Home (dark and light), the stock page and Settings. **Do not start plan 2** (porting Markets, Smart Money, Screener, News, Portfolio, the remaining 13 blocks, chart/financials/holders/news tabs, chip actions, tracked managers, Home tab create/rename and layout snapshots, then deleting `/classic`) until he approves the shell.
