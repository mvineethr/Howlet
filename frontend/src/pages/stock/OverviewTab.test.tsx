import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import OverviewTab from "./OverviewTab";
import type { SecurityDetail } from "../../lib/api";

afterEach(() => vi.restoreAllMocks());

const q = {
  symbol: "AAPL", name: "Apple Inc.", price: 100, change: 1, change_pct: 1, previous_close: 99, currency: "USD",
  day_low: 98, day_high: 101, week52_low: 80, week52_high: 120, volume: 1000, exchange: "NasdaqGS",
  instrument_type: "EQUITY", range: "6mo", range_change_pct: -2.5, history_ts: [], history_open: [], history_high: [],
  history_low: [], history_close: [], history_volume: [], studies: { sma20: 101.234, sma50: null }, orb: null,
} as unknown as SecurityDetail;

test("quote, studies, ORB-unavailable and events render; dates stay raw", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    symbol: "AAPL", next_earnings_date: "2026-11-02", analyst_recommendation: "hold",
    analyst_counts: { strong_buy: 6, buy: 18, hold: 14, sell: 3, strong_sell: 3 },
    shareholder_meetings: [{ form: "DEF 14A", filing_date: "2026-01-08", accession_number: "x" }],
  })));
  render(<FluentProvider theme={webDarkTheme}><OverviewTab symbol="AAPL" q={q} /></FluentProvider>);
  expect(screen.getByText("Range change (6mo)")).toBeTruthy();
  expect(screen.getByText("-2.50%")).toBeTruthy();
  expect(screen.getByText("101.23")).toBeTruthy();
  expect(screen.getByText(/ORB unavailable/)).toBeTruthy();
  await waitFor(() => expect(screen.getByText("2026-11-02")).toBeTruthy());
  expect(screen.getByText("hold")).toBeTruthy();
  expect(screen.getByText(/Strong buy 6 · Buy 18 · Hold 14 · Sell 3 · Strong sell 3/)).toBeTruthy();
  expect(screen.getByText("DEF 14A · 2026-01-08")).toBeTruthy();
});
