import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import ManagersTab from "./ManagersTab";

afterEach(() => vi.restoreAllMocks());
const json = (b: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(b), { status }));

test("holdings, allocation, changes load; diff failure shows its SEC error alone", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const u = String(input);
    if (u.startsWith("/api/managers")) return json([{ label: "buffett", cik: "1067983" }]);
    if (u.startsWith("/api/portfolio")) return json({ identifier: "buffett", cik: "0001067983", period_of_report: "2026-06-30",
      filing_date: "2026-08-14", accession_number: "a", total_value_usd: 3e11, position_count: 2, positions: [
        { issuer: "APPLE INC", cusip: "037833100", value_usd: 6.6e10, shares: 227917808, share_type: "SH", weight_pct: 22.04, ticker: "AAPL", price: 347.73, change_pct: -0.14, currency: "USD", sparkline: [1, 2] },
        { issuer: "OBSCURE CO", cusip: "999999999", value_usd: 1e6, shares: 10, share_type: "SH", weight_pct: 0.01, ticker: null, price: null, change_pct: null, currency: null, sparkline: [] },
      ] });
    if (u.startsWith("/api/diff")) return json({ error: "Need 2 filings to diff" }, 404);
    return json([]);
  });
  render(<FluentProvider theme={webDarkTheme}><ManagersTab manager="buffett" /></FluentProvider>);
  await waitFor(() => expect(screen.getAllByText("APPLE INC").length).toBeGreaterThan(0));
  expect(screen.getByText(/CIK 0001067983 · period 2026-06-30 · filed 2026-08-14 · 2 positions · \$300\.00B/)).toBeTruthy();
  expect(screen.getAllByText("22.0%").length).toBeGreaterThan(0);
  expect(screen.getAllByText("OBSCURE CO").length).toBeGreaterThan(0); // allocation falls back to issuer
  await waitFor(() => expect(screen.getByText("Need 2 filings to diff")).toBeTruthy());
});
