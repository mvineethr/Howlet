import { readJson, writeJson } from "./storage";

export type Holding = { symbol: string; shares: number };
export const HOLDINGS_KEY = "howlet_pf_holdings"; // classic shape [{symbol, shares}]

const ok = (h: unknown): h is Holding =>
  !!h && typeof h === "object" && typeof (h as Holding).symbol === "string" &&
  Number.isFinite((h as Holding).shares) && (h as Holding).shares > 0;

export const loadHoldings = (): Holding[] =>
  readJson<unknown[]>(HOLDINGS_KEY, [], Array.isArray as (v: unknown) => v is unknown[]).filter(ok).map((h) => ({ symbol: h.symbol, shares: h.shares }));

export function upsertHolding(list: Holding[], rawSymbol: string, shares: number): Holding[] | { error: string } {
  const symbol = rawSymbol.trim().toUpperCase();
  if (!symbol) return { error: "Enter a symbol." };
  if (!Number.isFinite(shares) || shares <= 0) return { error: "Shares must be a positive number." };
  return list.some((h) => h.symbol === symbol)
    ? list.map((h) => (h.symbol === symbol ? { symbol, shares } : h))
    : [...list, { symbol, shares }];
}

export const removeHolding = (list: Holding[], symbol: string): Holding[] => list.filter((h) => h.symbol !== symbol);
export const saveHoldings = (list: Holding[]): void => writeJson(HOLDINGS_KEY, list);
