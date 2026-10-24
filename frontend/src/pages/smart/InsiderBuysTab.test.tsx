import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import InsiderBuysTab, { stockSymbols } from "./InsiderBuysTab";

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

test("stockSymbols drops indices, FX, futures and crypto", () => {
  expect(stockSymbols(["AAPL", "^GSPC", "EURUSD=X", "CL=F", "BTC-USD", "BRK-B"])).toEqual(["AAPL", "BRK-B"]);
});

test("scans the default list's stock symbols and renders buys", async () => {
  localStorage.setItem("howlet_watchlists_v1", JSON.stringify({ default: ["AAPL", "^GSPC", "MSFT"] }));
  const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    symbols_scanned: ["AAPL", "MSFT"], filings_per_symbol: 8,
    summary: [{ symbol: "MSFT", buy_count: 2, total_shares: 100, total_value_usd: 2e6, latest_date: "2026-10-01" }],
    buys: [{ symbol: "MSFT", insider: "Jane Doe", relationship: "Director", date: "2026-10-01", shares: 50, price_per_share: 400,
      value_usd: 20000, shares_owned_after: 1000, filing_date: "2026-10-02", accession_number: "x" }],
  })));
  render(<FluentProvider theme={webDarkTheme}><InsiderBuysTab /></FluentProvider>);
  await waitFor(() => expect(screen.getByText("Jane Doe")).toBeTruthy());
  expect(String(f.mock.calls[0][0])).toContain("symbols=AAPL%2CMSFT");
  expect(screen.getByText("MSFT 2× $2.0M")).toBeTruthy();
});
