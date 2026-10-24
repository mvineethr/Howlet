import { formatRoute, parseHash, visibleRail } from "./route";
import { DEFAULT_SETTINGS } from "./settings";

test("parses pages, stocks and junk", () => {
  expect(parseHash("#/news", "home")).toEqual({ kind: "page", page: "news" });
  expect(parseHash("#/stock/brk-b", "home")).toEqual({ kind: "stock", symbol: "BRK-B", tab: "overview" });
  expect(parseHash("#/stock/AAPL/holders", "home")).toEqual({ kind: "stock", symbol: "AAPL", tab: "holders" });
  expect(parseHash("#/stock/AAPL/bogus", "home")).toEqual({ kind: "stock", symbol: "AAPL", tab: "overview" });
  expect(parseHash("", "markets")).toEqual({ kind: "page", page: "markets" });
  expect(parseHash("#/nope", "home")).toEqual({ kind: "page", page: "home" });
});

test("format round-trips", () => {
  const r = { kind: "stock", symbol: "^GSPC", tab: "chart" } as const;
  expect(parseHash(formatRoute(r), "home")).toEqual(r);
});

test("visibleRail respects order and hidden pages", () => {
  const s = { ...DEFAULT_SETTINGS, railOrder: ["news" as const, ...DEFAULT_SETTINGS.railOrder.filter((p) => p !== "news")], railHidden: ["screener" as const] };
  const rail = visibleRail(s);
  expect(rail[0]).toBe("news");
  expect(rail).not.toContain("screener");
});
