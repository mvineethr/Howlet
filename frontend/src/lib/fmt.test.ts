import { ago, fmtInt, fmtMoney, fmtNum, priceDigits, safeHref, signed, tone } from "./fmt";

test("fmtNum / fmtInt", () => {
  expect(fmtNum(1234.5)).toBe("1,234.50");
  expect(fmtNum(0.12345, 4)).toBe("0.1235");
  expect(fmtNum(null)).toBe("—");
  expect(fmtNum(NaN)).toBe("—");
  expect(fmtInt(1234567.4)).toBe("1,234,567");
  expect(fmtInt(undefined)).toBe("—");
});

test("fmtMoney scales and signs", () => {
  expect(fmtMoney(1.5e12)).toBe("$1.50T");
  expect(fmtMoney(2.345e9)).toBe("$2.35B");
  expect(fmtMoney(-95e6)).toBe("-$95.0M");
  expect(fmtMoney(12345)).toBe("$12,345");
  expect(fmtMoney(null)).toBe("—");
});

test("signed, tone, priceDigits", () => {
  expect(signed(1.234)).toBe("+1.23");
  expect(signed(-1.2, 1)).toBe("-1.2");
  expect(signed(0)).toBe("0.00");
  expect(signed(null)).toBe("—");
  expect(tone(2)).toBe("var(--up)");
  expect(tone(-2)).toBe("var(--down)");
  expect(tone(0)).toBe("var(--dim)");
  expect(tone(null)).toBe("var(--dim)");
  expect(priceDigits(0.9991)).toBe(4);
  expect(priceDigits(80728)).toBe(2);
});

test("ago and safeHref", () => {
  const now = Date.parse("2026-10-24T12:00:00Z");
  expect(ago("2026-10-24T11:55:00Z", now)).toBe("5m");
  expect(ago("2026-10-24T09:00:00Z", now)).toBe("3h");
  expect(ago("2026-10-22T12:00:00Z", now)).toBe("2d");
  expect(ago(null, now)).toBe("");
  expect(safeHref("https://x.com/a")).toBe("https://x.com/a");
  expect(safeHref("javascript:alert(1)")).toBeUndefined();
  expect(safeHref(null)).toBeUndefined();
});
