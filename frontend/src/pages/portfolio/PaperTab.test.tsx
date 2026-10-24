import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import PaperTab from "./PaperTab";

const order = (over: object) => ({ id: "o1", ts: "2026-10-23T14:00:00+00:00", symbol: "AAPL", side: "buy", qty: 2, type: "limit",
  limit: 180, stop: null, tif: "day", status: "open", fill: null, reason: null, ref_price: 200, closed_at: null, ...over });
const ACCOUNT = {
  account: { id: "a", created: "2026-10-21T14:00:00+00:00", start_cash: 10000 }, cash: 8000,
  positions: [{ symbol: "AAPL", qty: 10, avg_cost: 200, cost_basis: 2000, price: 210, value: 2100, unrealized: 100, unrealized_pct: 5 }],
  positions_value: 2100, equity: 10100, day_change: 25, total_return_pct: 1, realized_pnl: 0,
  open_orders: [order({})],
  activity: [order({ id: "o2", qty: 3, status: "rejected", reason: "Not enough cash when it triggered at $105.00.", closed_at: "2026-10-23T15:00:00+00:00" })],
  market_open: false, prices_unavailable: [],
};
const HISTORY = { dates: ["2026-10-21", "2026-10-22"], account: [10000, 10100], spy: [10000, 10200], account_return_pct: 1, spy_return_pct: 2 };

function mockFetch(account: unknown) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (init?.method === "DELETE") return new Response(JSON.stringify(order({ status: "cancelled" })));
    if (init?.method === "POST") return new Response(JSON.stringify(ACCOUNT));
    if (url === "/api/paper/history") return new Response(JSON.stringify(HISTORY));
    return new Response(JSON.stringify(account));
  });
}
const renderTab = () => render(<FluentProvider theme={webDarkTheme}><PaperTab /></FluentProvider>);
afterEach(() => vi.restoreAllMocks());

test("renders summary, vs-SPY, positions, open orders and activity reasons", async () => {
  mockFetch(ACCOUNT);
  renderTab();
  await waitFor(() => expect(screen.getByText("$10,100.00")).toBeTruthy());
  expect(screen.getByText("+1.0% vs S&P 500 +2.0%")).toBeTruthy();
  expect(screen.getByText("Buy 2 AAPL · limit $180.00 · day")).toBeTruthy();
  expect(screen.getByText("Not enough cash when it triggered at $105.00.")).toBeTruthy();
  expect(screen.getByRole("img", { name: "Account value vs S&P 500" })).toBeTruthy();
});

test("cancel calls DELETE and reloads", async () => {
  const f = mockFetch(ACCOUNT);
  renderTab();
  fireEvent.click(await screen.findByRole("button", { name: "Cancel order o1" }));
  await waitFor(() => expect(f.mock.calls.some(([u, i]) => String(u) === "/api/paper/orders/o1" && i?.method === "DELETE")).toBe(true));
});

test("no account: start form posts the chosen cash", async () => {
  const f = mockFetch({ account: null, market_open: false });
  renderTab();
  fireEvent.change(await screen.findByLabelText("Starting cash"), { target: { value: "25000" } });
  fireEvent.click(screen.getByRole("button", { name: "Start paper account" }));
  await waitFor(() => {
    const post = f.mock.calls.find(([u, i]) => String(u) === "/api/paper/reset" && i?.method === "POST");
    expect(post && JSON.parse(String(post[1]!.body))).toEqual({ start_cash: 25000 });
  });
});
