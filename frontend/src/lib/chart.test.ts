import { barsFromSecurity, chartStyles, CHART_RANGES, INDICATORS, MAIN_PANE } from "./chart";
import type { SecurityDetail } from "./api";

test("bars convert seconds to ms and keep OHLCV aligned", () => {
  const s = { history_ts: [1, 2], history_open: [10, 11], history_high: [12, 13], history_low: [9, 10],
    history_close: [11, 12], history_volume: [100, 200] } as unknown as SecurityDetail;
  expect(barsFromSecurity(s)).toEqual([
    { timestamp: 1000, open: 10, high: 12, low: 9, close: 11, volume: 100 },
    { timestamp: 2000, open: 11, high: 13, low: 10, close: 12, volume: 200 },
  ]);
});

test("styles come from the CSS variables, not literals", () => {
  const vars: Record<string, string> = { "--up": "U", "--down": "D", "--hair": "H", "--text": "T", "--dim": "M",
    "--border": "B", "--accent": "A", "--bg": "G", "--cyan": "C" };
  const st = chartStyles((n) => vars[n]) as any;
  expect(st.candle.bar.upColor).toBe("U");
  expect(st.candle.bar.downWickColor).toBe("D");
  expect(st.grid.horizontal.color).toBe("H");
  expect(st.crosshair.horizontal.text.backgroundColor).toBe("A");
  expect(st.overlay.line.color).toBe("C");
  expect(JSON.stringify(st)).not.toMatch(/#[0-9a-f]{3,6}/i);
});

test("catalogue sanity", () => {
  expect(CHART_RANGES).toContain("6mo");
  expect(INDICATORS.filter((i) => i.main).map((i) => i.name)).toEqual(MAIN_PANE);
  expect(INDICATORS.find((i) => i.name === "WR")?.label).toBe("Williams %R");
});
