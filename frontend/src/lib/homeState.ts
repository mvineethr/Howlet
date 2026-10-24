import { HOME_KEY, type HomeState } from "./legacy";
import { readJson, writeJson } from "./storage";

type Err = { error: string };
export type Snapshots = Record<string, HomeState>;
export const SNAPSHOTS_KEY = "howlet_home_snapshots_v1";

export function addTab(h: HomeState, rawName: string): HomeState | Err {
  const name = rawName.trim();
  if (!name) return { error: "Name the tab." };
  const id = `t${Date.now().toString(36)}`;
  return { tabs: [...h.tabs, { id, name, blocks: [] }], active: id };
}

export function renameTab(h: HomeState, id: string, rawName: string): HomeState | Err {
  const name = rawName.trim();
  if (!name) return { error: "Name the tab." };
  return { ...h, tabs: h.tabs.map((t) => (t.id === id ? { ...t, name } : t)) };
}

export function deleteTab(h: HomeState, id: string): HomeState {
  if (id === "home" || h.tabs.length < 2 || !h.tabs.some((t) => t.id === id)) return h;
  const tabs = h.tabs.filter((t) => t.id !== id);
  return { tabs, active: h.active === id ? tabs[0].id : h.active };
}

export function resetHome(first: () => HomeState): HomeState {
  const h = first();
  writeJson(HOME_KEY, h);
  return h;
}

const validHome = (v: unknown): v is HomeState =>
  !!v && typeof v === "object" && Array.isArray((v as HomeState).tabs) && (v as HomeState).tabs.length > 0;

export function loadSnapshots(): Snapshots {
  const all = readJson<Snapshots>(SNAPSHOTS_KEY, {}, (v): v is Snapshots =>
    !!v && typeof v === "object" && !Array.isArray(v));
  return Object.fromEntries(Object.entries(all).filter(([, v]) => validHome(v)));
}

export function saveSnapshot(s: Snapshots, rawName: string, h: HomeState): Snapshots | Err {
  const name = rawName.trim().toLowerCase();
  if (!name) return { error: "Name the layout." };
  return { ...s, [name]: structuredClone(h) };
}

export function deleteSnapshot(s: Snapshots, name: string): Snapshots {
  const { [name]: _drop, ...rest } = s;
  return rest;
}

export function applySnapshot(snap: HomeState): HomeState {
  const h = structuredClone(snap);
  return h.tabs.some((t) => t.id === h.active) ? h : { ...h, active: h.tabs[0].id };
}
