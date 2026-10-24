import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import OrderTicket from "./OrderTicket";

const ACCOUNT = { account: { id: "a", created: "2026-10-23T14:00:00+00:00", start_cash: 10000 }, cash: 10000, positions: [],
  positions_value: 0, equity: 10000, day_change: 0, total_return_pct: 0, realized_pnl: 0, open_orders: [], activity: [],
  market_open: false, prices_unavailable: [] };

function mockFetch(order: { status: number; body: unknown }) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (init?.method === "POST") return new Response(JSON.stringify(order.body), { status: order.status });
    if (url.startsWith("/api/quotes")) return new Response(JSON.stringify([{ symbol: "AAPL", price: 200 }]));
    return new Response(JSON.stringify(ACCOUNT));
  });
}

const renderTicket = (props: Partial<Parameters<typeof OrderTicket>[0]> = {}) =>
  render(<FluentProvider theme={webDarkTheme}><OrderTicket open symbol="AAPL" onClose={() => {}} {...props} /></FluentProvider>);

afterEach(() => vi.restoreAllMocks());

test("shows a live estimate and the cash left", async () => {
  mockFetch({ status: 201, body: {} });
  renderTicket();
  fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "5" } });
  await waitFor(() => expect(screen.getByText(/Estimated cost \$1,000\.00/)).toBeTruthy());
  expect(screen.getByText(/Cash after: \$9,000\.00/)).toBeTruthy();
});

test("switching to limit shows the explainer and posts the right body", async () => {
  const f = mockFetch({ status: 201, body: { id: "x", status: "open" } });
  const onPlaced = vi.fn();
  renderTicket({ onPlaced });
  fireEvent.click(screen.getByLabelText("Limit"));
  fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Limit price"), { target: { value: "180" } });
  expect(screen.getByText("Buy limit: fills only if the price drops to $180.00 or lower.")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Place paper order" }));
  await waitFor(() => expect(onPlaced).toHaveBeenCalled());
  const post = f.mock.calls.find(([, init]) => init?.method === "POST")!;
  expect(JSON.parse(String(post[1]!.body))).toEqual({ symbol: "AAPL", side: "buy", qty: 2, type: "limit", limit: 180, stop: null, tif: "day" });
});

test("dollar mode converts to whole-cent-safe shares", async () => {
  const f = mockFetch({ status: 201, body: { id: "x" } });
  renderTicket();
  fireEvent.click(screen.getByLabelText("Dollars"));
  await waitFor(() => expect(f).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText("Amount in dollars"), { target: { value: "1000" } });
  await waitFor(() => expect(screen.getByText(/= 5 shares/)).toBeTruthy());
});

test("server errors show inline and keep the dialog open", async () => {
  mockFetch({ status: 400, body: { error: "Not enough cash: this needs $2,000.00 and $1.00 is available." } });
  const onClose = vi.fn();
  renderTicket({ onClose });
  fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "10" } });
  fireEvent.click(screen.getByRole("button", { name: "Place paper order" }));
  await waitFor(() => expect(screen.getByText(/Not enough cash/)).toBeTruthy());
  expect(onClose).not.toHaveBeenCalled();
});
