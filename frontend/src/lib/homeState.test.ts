import { beforeEach, describe, expect, it } from "vitest";
import type { HomeState } from "./legacy";
import { HOME_KEY } from "./legacy";
import {
  SNAPSHOTS_KEY, addTab, applySnapshot, deleteSnapshot, deleteTab, loadSnapshots, renameTab, resetHome, saveSnapshot,
} from "./homeState";

const base = (): HomeState => ({
  active: "home",
  tabs: [{ id: "home", name: "Home", blocks: [{ i: "a", type: "pulse", config: {}, x: 0, y: 0, w: 4, h: 4 }] },
    { id: "t2", name: "Two", blocks: [] }],
});

describe("tabs", () => {
  it("add: empty name errors, new tab becomes active, input untouched", () => {
    const h = base();
    expect(addTab(h, "  ")).toEqual({ error: "Name the tab." });
    const r = addTab(h, " Macro ") as HomeState;
    expect(r.tabs).toHaveLength(3);
    expect(r.tabs[2].name).toBe("Macro");
    expect(r.active).toBe(r.tabs[2].id);
    expect(h.tabs).toHaveLength(2);
  });
  it("rename: empty errors, trims", () => {
    expect(renameTab(base(), "t2", "")).toEqual({ error: "Name the tab." });
    const r = renameTab(base(), "t2", " New ") as HomeState;
    expect(r.tabs[1].name).toBe("New");
  });
  it("delete: home and last tab protected; active falls back", () => {
    const h = base();
    expect(deleteTab(h, "home")).toBe(h);
    const only: HomeState = { active: "x", tabs: [{ id: "x", name: "X", blocks: [] }] };
    expect(deleteTab(only, "x")).toBe(only);
    const r = deleteTab({ ...h, active: "t2" }, "t2");
    expect(r.tabs.map((t) => t.id)).toEqual(["home"]);
    expect(r.active).toBe("home");
    expect(deleteTab(h, "t2").active).toBe("home");
  });
});

describe("snapshots", () => {
  beforeEach(() => localStorage.clear());
  it("round trip with deep copies", () => {
    expect(saveSnapshot({}, " ", base())).toEqual({ error: "Name the layout." });
    const s = saveSnapshot({}, " Work ", base()) as Record<string, HomeState>;
    expect(Object.keys(s)).toEqual(["work"]);
    localStorage.setItem(SNAPSHOTS_KEY, JSON.stringify(s));
    expect(Object.keys(loadSnapshots())).toEqual(["work"]);
    const applied = applySnapshot(s.work);
    applied.tabs[0].blocks[0].w = 99;
    s.work.tabs[0].name = "mutated";
    expect(applySnapshot(s.work).tabs[0].blocks[0].w).toBe(4);
    expect(Object.keys(deleteSnapshot(s, "work"))).toEqual([]);
    expect(s.work).toBeDefined();
  });
  it("saveSnapshot copies the home it is given", () => {
    const h = base();
    const s = saveSnapshot({}, "a", h) as Record<string, HomeState>;
    h.tabs[0].name = "changed";
    expect(s.a.tabs[0].name).toBe("Home");
  });
  it("applySnapshot active falls back to first tab", () => {
    expect(applySnapshot({ ...base(), active: "gone" }).active).toBe("home");
  });
  it("loadSnapshots skips snapshots with empty or non-array tabs", () => {
    localStorage.setItem(SNAPSHOTS_KEY, JSON.stringify({
      ok: base(), empty: { tabs: [], active: "x" }, bad: { tabs: "no", active: "x" }, nul: null,
    }));
    expect(Object.keys(loadSnapshots())).toEqual(["ok"]);
  });
  it("loadSnapshots tolerates junk", () => {
    localStorage.setItem(SNAPSHOTS_KEY, "[1]");
    expect(loadSnapshots()).toEqual({});
  });
});

describe("resetHome", () => {
  it("writes and returns the default", () => {
    const r = resetHome(base);
    expect(JSON.parse(localStorage.getItem(HOME_KEY)!)).toEqual(r);
  });
});
