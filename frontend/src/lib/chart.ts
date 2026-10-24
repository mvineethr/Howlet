import type { SecurityDetail } from "./api";

export const CHART_RANGES = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "5y", "max"] as const;
export const MAIN_PANE = ["MA", "EMA", "BOLL", "SAR", "BBI"];
export const INDICATORS: { name: string; label: string; main: boolean }[] = [
  ...[["MA", "MA"], ["EMA", "EMA"], ["BOLL", "Bollinger"], ["SAR", "SAR"], ["BBI", "BBI"]].map(([name, label]) => ({ name, label, main: true })),
  ...[["VOL", "Volume"], ["MACD", "MACD"], ["RSI", "RSI"], ["KDJ", "KDJ"], ["OBV", "OBV"], ["CCI", "CCI"], ["WR", "Williams %R"],
    ["TRIX", "TRIX"], ["ROC", "ROC"], ["DMI", "DMI"], ["MTM", "Momentum"], ["PSY", "PSY"]].map(([name, label]) => ({ name, label, main: false })),
];
export const DRAW_TOOLS: [string, string][] = [
  ["segment", "Line"], ["rayLine", "Ray"], ["horizontalStraightLine", "H-line"], ["priceLine", "Price"],
  ["priceChannelLine", "Channel"], ["fibonacciLine", "Fib"], ["simpleAnnotation", "Note"],
];

export type Bar = { timestamp: number; open: number; high: number; low: number; close: number; volume: number };

export const barsFromSecurity = (s: SecurityDetail): Bar[] =>
  s.history_ts.map((t, i) => ({
    timestamp: t * 1000, open: s.history_open[i], high: s.history_high[i], low: s.history_low[i],
    close: s.history_close[i], volume: s.history_volume[i],
  }));

// Inventory §2b mapping; every colour is read from a CSS variable at call time.
export function chartStyles(v: (name: string) => string): object {
  const up = v("--up"), down = v("--down"), dim = v("--dim");
  return {
    grid: { horizontal: { color: v("--hair") }, vertical: { color: v("--hair") } },
    candle: {
      bar: { upColor: up, downColor: down, upBorderColor: up, downBorderColor: down, upWickColor: up, downWickColor: down },
      priceMark: { last: { upColor: up, downColor: down } },
      tooltip: { text: { color: v("--text") } },
    },
    indicator: { tooltip: { text: { color: dim } } },
    xAxis: { tickText: { color: dim } },
    yAxis: { tickText: { color: dim } },
    separator: { color: v("--border") },
    crosshair: {
      horizontal: { line: { color: dim }, text: { backgroundColor: v("--accent"), color: v("--bg") } },
      vertical: { line: { color: dim }, text: { backgroundColor: v("--accent"), color: v("--bg") } },
    },
    overlay: {
      point: { color: v("--accent"), borderColor: v("--border") },
      line: { color: v("--cyan") },
      text: { color: v("--bg"), backgroundColor: v("--accent") },
    },
  };
}
