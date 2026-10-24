import { formatRoute, parseHash, visibleRail, type Route } from "./route";
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

test("malformed percent-encoding does not throw", () => {
  expect(parseHash("#/stock/100%", "home")).toEqual({ kind: "stock", symbol: "100%", tab: "overview" });
});

test("page params round-trip and are omitted when absent", () => {
  expect(parseHash("#/smart/managers/buffett", "home")).toEqual({ kind: "page", page: "smart", params: ["managers", "buffett"] });
  expect(parseHash("#/smart", "home")).toEqual({ kind: "page", page: "smart" });
  expect(parseHash("#/nope/x", "home")).toEqual({ kind: "page", page: "home" });
  const r: Route = { kind: "page", page: "smart", params: ["history", "BRK B"] };
  expect(formatRoute(r)).toBe("#/smart/history/BRK%20B");
  expect(parseHash(formatRoute(r), "home")).toEqual(r);
});
