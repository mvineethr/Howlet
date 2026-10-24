import { initialMarketsTab, MARKETS_TAB_KEY } from "./MarketsPage";

beforeEach(() => localStorage.clear());

test("new key wins; otherwise classic mode maps; never writes the classic key", () => {
  expect(initialMarketsTab()).toBe("stocks");
  localStorage.setItem("howlet_mkts_mode", "crypto");
  expect(initialMarketsTab()).toBe("crypto");
  localStorage.setItem(MARKETS_TAB_KEY, JSON.stringify("economy"));
  expect(initialMarketsTab()).toBe("economy");
  localStorage.setItem(MARKETS_TAB_KEY, JSON.stringify("bogus"));
  expect(initialMarketsTab()).toBe("crypto");
  expect(localStorage.getItem("howlet_mkts_mode")).toBe("crypto");
});
