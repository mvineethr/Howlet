import { readJson, writeJson } from "./storage";

export type PriceAlert = { id: string; sym: string; op: ">" | "<"; px: number; fired: { price: number; at: string } | null };
const KEY = "howlet_price_alerts_v1"; // legacy key, same shape

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
