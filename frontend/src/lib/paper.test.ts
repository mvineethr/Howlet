import { estimate, explain, orderLabel, parseNum, sharesFor, usd } from "./paper";
import type { PaperOrder } from "./api";

test("explains every order type in plain English", () => {
  expect(explain("buy", "limit", 180)).toBe("Buy limit: fills only if the price drops to $180.00 or lower.");
  expect(explain("sell", "limit", 210.5)).toBe("Sell limit: fills only if the price rises to $210.50 or higher.");
  expect(explain("sell", "stop", 150)).toContain("falls to $150.00 or lower");
  expect(explain("buy", "stop", null)).toContain("rises to your price or higher");
  expect(explain("buy", "market", null)).toContain("next session's opening price");
});

test("dollar amounts floor to 4 decimals so the cost never exceeds the amount", () => {
  expect(sharesFor(1000, 300)).toBe(3.3333);
  expect(sharesFor(1000, 300) * 300).toBeLessThanOrEqual(1000);
});

test("estimate uses the quote for market orders and the level otherwise", () => {
  expect(estimate("market", 2, 100, null)).toBe(200);
  expect(estimate("limit", 2, 100, 90)).toBe(180);
  expect(estimate("limit", 2, 100, null)).toBeNull();
  expect(estimate("market", 0, 100, null)).toBeNull();
});

test("parseNum, usd and orderLabel", () => {
  expect(parseNum(" 12.5 ")).toBe(12.5);
  expect(parseNum("")).toBeNull();
  expect(parseNum("abc")).toBeNull();
  expect(usd(-1234.5)).toBe("-$1,234.50");
  expect(usd(null)).toBe("—");
  const o = { side: "buy", qty: 10, symbol: "AAPL", type: "limit", limit: 180, stop: null, tif: "day" } as PaperOrder;
  expect(orderLabel(o)).toBe("Buy 10 AAPL · limit $180.00 · day");
});
