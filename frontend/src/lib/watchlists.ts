import { writeJson } from "./storage";

export type Watchlists = Record<string, string[]>;
export const WATCHLISTS_KEY = "howlet_watchlists_v1"; // legacy key, same shape

export function addSymbol(all: Watchlists, list: string, raw: string): Watchlists {
  const sym = raw.trim().toUpperCase();
  const cur = all[list] ?? [];
  if (!sym || cur.includes(sym)) return all;
  return { ...all, [list]: [...cur, sym] };
}

export const removeSymbol = (all: Watchlists, list: string, sym: string): Watchlists =>
  ({ ...all, [list]: (all[list] ?? []).filter((s) => s !== sym) });

export function createList(all: Watchlists, raw: string): { all: Watchlists; name: string } | { error: string } {
  const name = raw.trim().toLowerCase();
  if (!name) return { error: "Name the list." };
  if (name in all) return { error: "That list already exists." };
  return { all: { ...all, [name]: [] }, name };
}

export function deleteList(all: Watchlists, name: string): Watchlists {
  if (name === "default" || Object.keys(all).length <= 1 ||!(name in all)) return all;
  const { [name]: _gone, ...rest } = all;
  return rest;
}

export const saveWatchlists = (all: Watchlists) => writeJson(WATCHLISTS_KEY, all);
