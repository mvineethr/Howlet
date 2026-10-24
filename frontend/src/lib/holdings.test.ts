import { HOLDINGS_KEY, loadHoldings, removeHolding, saveHoldings, upsertHolding } from "./holdings";

beforeEach(() => localStorage.clear());

test("load keeps only valid entries", () => {
  localStorage.setItem(HOLDINGS_KEY, JSON.stringify([{ symbol: "AAPL", shares: 10 }, { symbol: "X", shares: -1 }, null, { symbol: 5 }]));
  expect(loadHoldings()).toEqual([{ symbol: "AAPL", shares: 10 }]);
  localStorage.setItem(HOLDINGS_KEY, "{}");
  expect(loadHoldings()).toEqual([]);
});

test("upsert replaces shares, validates input; remove; save shape", () => {
  const a = upsertHolding([], " aapl ", 10) as { symbol: string; shares: number }[];
  expect(a).toEqual([{ symbol: "AAPL", shares: 10 }]);
  expect(upsertHolding(a, "AAPL", 5)).toEqual([{ symbol: "AAPL", shares: 5 }]);
  expect(upsertHolding(a, "", 5)).toEqual({ error: "Enter a symbol." });
  expect(upsertHolding(a, "MSFT", 0)).toEqual({ error: "Shares must be a positive number." });
  expect(upsertHolding(a, "MSFT", NaN)).toEqual({ error: "Shares must be a positive number." });
  expect(removeHolding(a, "AAPL")).toEqual([]);
  saveHoldings(a);
  expect(JSON.parse(localStorage.getItem(HOLDINGS_KEY)!)).toEqual([{ symbol: "AAPL", shares: 10 }]);
});
