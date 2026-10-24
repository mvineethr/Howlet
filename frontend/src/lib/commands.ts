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
