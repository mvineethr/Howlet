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
  expect(blockFor("fx-matrix").label).toBe("fx-matrix");
});
