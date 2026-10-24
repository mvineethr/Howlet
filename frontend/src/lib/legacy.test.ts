import { getWatchlists, loadHome, migrateLayout, HOME_KEY } from "./legacy";

beforeEach(() => localStorage.clear());

test("watchlists: named store wins, then legacy single list, then defaults", () => {
  localStorage.setItem("howlet_watchlist", JSON.stringify(["IBM"]));
  expect(getWatchlists()).toEqual({ default: ["IBM"] });
  localStorage.setItem("howlet_watchlists_v1", JSON.stringify({ tech: ["NVDA"] }));
  expect(getWatchlists()).toEqual({ tech: ["NVDA"] });
  localStorage.clear();
  expect(getWatchlists().default).toContain("AAPL");
});

test("migrateLayout packs widgets into a 12-col grid", () => {
  const legacy = {
    active: "home",
    tabs: [{ id: "home", name: "HOME", widgets: [
      { id: "a", type: "watchlist", config: { list: "default" } },
      { id: "b", type: "consensus", config: {}, tall: true },
      { id: "c", type: "world-markets", config: {}, wide: true },
    ] }],
  };
  const home = migrateLayout(legacy)!;
  const [a, b, c] = home.tabs[0].blocks;
  expect([a.x, a.y, a.w, a.h]).toEqual([0, 0, 6, 8]);
  expect([b.x, b.y, b.w, b.h]).toEqual([6, 0, 6, 16]);
  expect([c.x, c.w]).toEqual([0, 12]);
  expect(c.y).toBeGreaterThanOrEqual(16);
  expect(a.config).toEqual({ list: "default" });
});

test("migrateLayout rejects junk", () => {
  expect(migrateLayout({ tabs: "x" })).toBeNull();
  expect(migrateLayout(null)).toBeNull();
});

test("loadHome prefers new key, then non-empty legacy, then first run", () => {
  const first = () => ({ tabs: [{ id: "home", name: "Home", blocks: [] }], active: "home" });
  localStorage.setItem("howlet_layout_v1", JSON.stringify({ active: "home", tabs: [{ id: "home", name: "HOME", widgets: [] }] }));
  expect(loadHome(first)).toEqual(first()); // empty legacy -> first run
  expect(JSON.parse(localStorage.getItem(HOME_KEY)!)).toEqual(first());
  localStorage.setItem(HOME_KEY, JSON.stringify({ tabs: [{ id: "t", name: "Mine", blocks: [] }], active: "t" }));
  expect(loadHome(first).active).toBe("t");
});

test("migrateLayout skips junk widget entries", () => {
  const home = migrateLayout({ tabs: [{ id: "t", widgets: [null, 5, { id: "a", type: "watchlist" }] }] })!;
  expect(home.tabs[0].blocks.map((b) => b.i)).toEqual(["a"]);
});
