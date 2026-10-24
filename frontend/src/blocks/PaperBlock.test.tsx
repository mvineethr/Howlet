import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import type { ReactElement } from "react";
import PaperBlock from "./PaperBlock";

afterEach(() => vi.restoreAllMocks());
const wrap = (el: ReactElement) => render(<FluentProvider theme={webDarkTheme}>{el}</FluentProvider>);

test("summary and top positions, removable", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    account: { id: "a", created: "x", start_cash: 10000 }, cash: 8000, equity: 10100, day_change: -12.5, total_return_pct: 1,
    positions: [{ symbol: "AAPL", qty: 10, avg_cost: 200, cost_basis: 2000, price: 210, value: 2100, unrealized: 100, unrealized_pct: 5 }],
    positions_value: 2100, realized_pnl: 0, open_orders: [], activity: [], market_open: false, prices_unavailable: [],
  })));
  wrap(<PaperBlock onRemove={() => {}} />);
  await waitFor(() => expect(screen.getByText("$10,100.00")).toBeTruthy());
  expect(screen.getByText("-$12.50 today")).toBeTruthy();
  expect(screen.getByText("AAPL")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Remove Paper account" })).toBeTruthy();
});

test("no account yet points to the Paper tab", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ account: null, market_open: false })));
  wrap(<PaperBlock />);
  await waitFor(() => expect(screen.getByText(/No paper account yet/)).toBeTruthy());
});
