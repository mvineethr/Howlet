import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import PositionHistoryTab from "./PositionHistoryTab";

afterEach(() => vi.restoreAllMocks());

test("quarters render oldest first with share deltas", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    if (String(input).startsWith("/api/managers")) return Promise.resolve(new Response("[]"));
    return Promise.resolve(new Response(JSON.stringify({ identifier: "buffett", cik: "1", query: "AAPL", issuer: "APPLE INC", cusips: ["037833100"],
      quarters: [
        { period_of_report: "2025-12-31", filing_date: "2026-02-17", shares: 300, value_usd: 3e10, weight_pct: 25, held: true },
        { period_of_report: "2026-03-31", filing_date: "2026-05-15", shares: 250, value_usd: 2e10, weight_pct: 20, held: true },
      ] })));
  });
  render(<FluentProvider theme={webDarkTheme}><PositionHistoryTab manager="buffett" query="AAPL" /></FluentProvider>);
  await waitFor(() => expect(screen.getByText("APPLE INC · CUSIP 037833100")).toBeTruthy());
  expect(screen.getByText("2025-12-31")).toBeTruthy();
  expect(screen.getByText("(-50)")).toBeTruthy();
  expect(screen.getByText("25.0%")).toBeTruthy();
});
