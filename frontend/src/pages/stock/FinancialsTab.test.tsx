import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import FinancialsTab from "./FinancialsTab";

afterEach(() => vi.restoreAllMocks());
const wrap = (ui: JSX.Element) => render(<FluentProvider theme={webDarkTheme}>{ui}</FluentProvider>);

test("renders fiscal years with money formatting and raw end dates", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ symbol: "AAPL", cik: "1", company: "Apple Inc.",
    fiscal_years: [{ fiscal_year: 2025, end_date: "2025-09-27", revenue: 416161000000, net_income: -1e9, eps_diluted: 7.46,
      total_assets: 359241000000, total_liabilities: null, stockholders_equity: 73733000000, operating_cash_flow: 111482000000 }] })));
  wrap(<FinancialsTab symbol="AAPL" />);
  await waitFor(() => expect(screen.getByText("FY2025")).toBeTruthy());
  expect(screen.getByText("2025-09-27")).toBeTruthy();
  expect(screen.getByText("$416.16B")).toBeTruthy();
  expect(screen.getByText("-$1.00B")).toBeTruthy();
  expect(screen.getByText("7.46")).toBeTruthy();
  expect(screen.getByText("Annual financials · Apple Inc.")).toBeTruthy();
});

test("SEC error text is shown", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: "No SEC filer for ZZZZ" }), { status: 404 }));
  wrap(<FinancialsTab symbol="ZZZZ" />);
  await waitFor(() => expect(screen.getByText("No SEC filer for ZZZZ")).toBeTruthy());
});
