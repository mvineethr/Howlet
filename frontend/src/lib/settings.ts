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
