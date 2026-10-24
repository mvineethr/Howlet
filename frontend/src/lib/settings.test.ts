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
