import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import HoldersTab from "./HoldersTab";
import { clearHoldersMemo } from "../../lib/api";

afterEach(() => { vi.restoreAllMocks(); clearHoldersMemo(); });
const json = (b: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(b), { status }));

test("three panels load independently; P/S colouring; empty holders text names managers", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const u = String(input);
    if (u.startsWith("/api/holders")) return json({ symbol: "ZZ", tracked_managers: ["buffett", "ackman"], holders: [] });
    if (u.startsWith("/api/insiders")) return json({ symbol: "ZZ", company: "Z", filings_scanned: 3,
      summary: { open_market_purchases: 1, purchase_value_usd: 5e6, open_market_sales: 0, sale_value_usd: 0 },
      transactions: [{ insider: "Jane Doe", relationship: "CEO", date: "2026-10-20", code: "P", code_label: "Open-market purchase",
        shares: 1000, price_per_share: 50, value_usd: 50000, filing_date: "2026-10-22", accession_number: "a1" }] });
    return json({ error: "EDGAR down" }, 502);
  });
  render(<FluentProvider theme={webDarkTheme}><HoldersTab symbol="ZZ" /></FluentProvider>);
  await waitFor(() => expect(screen.getByText(/None of the tracked managers \(buffett, ackman\) reported holding ZZ/)).toBeTruthy());
  expect(screen.getByText(/last 3 Form 4s · 1 buys \$5\.0M · 0 sells/)).toBeTruthy();
  const buy = screen.getByText("Open-market purchase");
  expect(buy.getAttribute("style")).toContain("var(--up)");
  expect(screen.getByText("2026-10-20")).toBeTruthy();
  await waitFor(() => expect(screen.getByText("EDGAR down")).toBeTruthy());
});
