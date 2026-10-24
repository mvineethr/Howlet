import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import OptionsTab from "./OptionsTab";

afterEach(() => vi.restoreAllMocks());

test("calls/puts render with IV as a percentage and ITM strikes emphasised", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    symbol: "AAPL", underlying_price: 347.73, expiration_dates: ["2026-10-26", "2026-11-02"], selected_expiration: "2026-10-26",
    calls: [{ contract_symbol: "C1", strike: 260, last_price: 87.15, bid: 85.8, ask: 89.45, volume: 3, open_interest: 4, implied_volatility: 2.1446, in_the_money: true }],
    puts: [],
  })));
  render(<FluentProvider theme={webDarkTheme}><OptionsTab symbol="AAPL" /></FluentProvider>);
  await waitFor(() => expect(screen.getByText("214.5%")).toBeTruthy());
  expect(screen.getByText("260.00").getAttribute("style")).toContain("var(--up)");
  expect(screen.getByText("No contracts.")).toBeTruthy();
  expect(screen.getByText(/Underlying/)).toBeTruthy();
});
