import { BLOCKS, blockFor, firstRunHome } from "./registry";

test("first run has the 4 calm blocks, no overlaps", () => {
  const home = firstRunHome();
  const blocks = home.tabs[0].blocks;
  expect(blocks.map((b) => b.type).sort()).toEqual(["manager-changes", "market-news", "pulse", "watchlist"]);
  for (const a of blocks) for (const b of blocks) {
    if (a === b) continue;
    const overlap = a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
    expect(overlap).toBe(false);
  }
});

test("every first-run type is registered; unknown types fall back", () => {
  for (const b of firstRunHome().tabs[0].blocks) expect(BLOCKS[b.type]).toBeDefined();
  expect(blockFor("nope").label).toBe("nope");
});

test("every classic widget type is registered with its needs", () => {
  const classic = ["manager-portfolio", "manager-changes", "consensus", "watchlist", "watchlist-news", "watchlist-events",
    "insiders", "insider-buys", "position-history", "market-news", "fed", "yield-curve", "world-markets", "crypto",
    "filings", "fx-matrix", "fund"];
  for (const t of classic) expect(BLOCKS[t], t).toBeDefined();
  expect(BLOCKS["position-history"].needs).toBe("manager-symbol");
  expect(BLOCKS.fund.needs).toBe("symbol");
  expect(BLOCKS.pulse.needs).toBeNull();
});
