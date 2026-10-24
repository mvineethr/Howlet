import { fmtNum } from "./fmt";
import type { PaperOrder } from "./api";

export type Side = "buy" | "sell";
export type OrderType = "market" | "limit" | "stop";

export const usd = (n: number | null | undefined): string =>
  n == null || Number.isNaN(n) ? "—" : `${n < 0 ? "-" : ""}$${fmtNum(Math.abs(n))}`;

export function explain(side: Side, type: OrderType, level: number | null): string {
  const p = level != null && level > 0 ? usd(level) : "your price";
  if (type === "market") return `Market ${side}: fills right away while the market is open, otherwise at the next session's opening price.`;
  if (type === "limit") return side === "buy"
    ? `Buy limit: fills only if the price drops to ${p} or lower.`
    : `Sell limit: fills only if the price rises to ${p} or higher.`;
  return side === "buy"
    ? `Buy stop: if the price rises to ${p} or higher, buys at the next available price — used to catch a breakout.`
    : `Sell stop: if the price falls to ${p} or lower, sells at the next available price — used to cap a loss.`;
}

/** Shares for a dollar amount, floored to 4 decimals so the cost never exceeds it. */
export const sharesFor = (dollars: number, price: number): number => Math.floor((dollars / price) * 1e4) / 1e4;

export function estimate(type: OrderType, qty: number, price: number | null, level: number | null): number | null {
  const p = type === "market" ? price : level;
  return p != null && p > 0 && qty > 0 ? qty * p : null;
}

export function parseNum(s: string): number | null {
  const t = s.trim();
  const n = Number(t);
  return t && Number.isFinite(n) ? n : null;
}

export function orderLabel(o: PaperOrder): string {
  const level = o.type === "limit" ? o.limit : o.type === "stop" ? o.stop : null;
  return `${o.side === "buy" ? "Buy" : "Sell"} ${o.qty} ${o.symbol} · ${o.type}${level != null ? ` ${usd(level)}` : ""} · ${o.tif}`;
}
