import { create } from "zustand";
import { PAGE_IDS, useSettings, type PageId, type Settings } from "./settings";

export type StockTab = "overview" | "chart" | "financials" | "holders" | "news" | "options";
const STOCK_TABS: StockTab[] = ["overview", "chart", "financials", "holders", "news", "options"];
export type Route = { kind: "page"; page: PageId } | { kind: "stock"; symbol: string; tab: StockTab };

export function parseHash(hash: string, fallback: PageId): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map((p) => { try { return decodeURIComponent(p); } catch { return p; } });
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
