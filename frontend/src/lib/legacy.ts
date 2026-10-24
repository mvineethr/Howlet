import { readJson, writeJson } from "./storage";

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const DEFAULT_WATCHLIST = ["AAPL", "MSFT", "NVDA", "AMZN", "TSLA", "^GSPC", "BTC-USD"];

export function getWatchlists(): Record<string, string[]> {
  const named = readJson<Record<string, string[]> | null>("howlet_watchlists_v1", null,
    (v): v is Record<string, string[]> => isObj(v));
  if (named && Object.keys(named).length) return named;
  const legacy = readJson<string[]>("howlet_watchlist", [], (v): v is string[] => Array.isArray(v));
  return { default: legacy.length ? legacy : DEFAULT_WATCHLIST };
}

export type LegacyWidget = { id: string; type: string; config: Record<string, string>; wide?: boolean; tall?: boolean };
export type HomeBlock = { i: string; type: string; config: Record<string, string>; x: number; y: number; w: number; h: number };
export type HomeTab = { id: string; name: string; blocks: HomeBlock[] };
export type HomeState = { tabs: HomeTab[]; active: string };
export const HOME_KEY = "howlet_home_v1";
const ALWAYS_WIDE = new Set(["world-markets"]); // legacy widget def: always wide

export function migrateLayout(legacy: unknown): HomeState | null {
  if (!isObj(legacy) || !Array.isArray(legacy.tabs)) return null;
  const tabs: HomeTab[] = [];
  for (const t of legacy.tabs) {
    if (!isObj(t) || typeof t.id !== "string" || !Array.isArray(t.widgets)) return null;
    const blocks: HomeBlock[] = [];
    let x = 0, y = 0, rowH = 0;
    for (const w of t.widgets as LegacyWidget[]) {
      if (!isObj(w) || typeof w.id !== "string" || typeof w.type !== "string") continue;
      const width = w.wide || ALWAYS_WIDE.has(w.type) ? 12 : 6;
      const h = w.tall ? 16 : 8;
      if (x + width > 12) { x = 0; y += rowH; rowH = 0; }
      blocks.push({ i: w.id, type: w.type, config: isObj(w.config) ? (w.config as Record<string, string>) : {}, x, y, w: width, h });
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
