import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import HoldingsTab from "./HoldingsTab";

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

test("POSTs holdings and renders the risk summary", async () => {
  localStorage.setItem("howlet_pf_holdings", JSON.stringify([{ symbol: "AAPL", shares: 10 }]));
  const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    portfolio_return_pct: 12.34, portfolio_annualized_volatility_pct: 25.1, portfolio_max_drawdown_pct: -18.2, sharpe_ratio: 0.87,
    positions: [{ symbol: "AAPL", weight_pct: 100, return_pct: 12.34, annualized_volatility_pct: 25.1, max_drawdown_pct: -18.2 }],
  })));
  render(<FluentProvider theme={webDarkTheme}><HoldingsTab /></FluentProvider>);
  await waitFor(() => expect(screen.getAllByText("+12.3%").length).toBeGreaterThan(0));
  const [url, init] = f.mock.calls[0];
  expect(url).toBe("/api/risk");
  expect(JSON.parse(String((init as RequestInit).body))).toEqual({ holdings: [{ symbol: "AAPL", shares: 10 }], range: "1y" });
  expect(screen.getByText("0.87")).toBeTruthy();
});

test("no holdings: hint and no request", () => {
  const f = vi.spyOn(globalThis, "fetch");
  render(<FluentProvider theme={webDarkTheme}><HoldingsTab /></FluentProvider>);
  expect(screen.getByText("Add positions to compute risk.")).toBeTruthy();
  expect(f).not.toHaveBeenCalled();
});
