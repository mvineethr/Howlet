import { render, screen, waitFor } from "@testing-library/react";
import OwlChips from "./OwlChips";

afterEach(() => vi.restoreAllMocks());
const reply = (body: unknown, status = 200) =>
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(body), { status }));

test("one chip per holder, heaviest first", async () => {
  reply({ symbol: "AAPL", tracked_managers: ["buffett", "lilu"], holders: [
    { manager: "lilu", weight_pct: 5.1, value_usd: 1, shares: 1, issuer: "APPLE", period_of_report: null },
    { manager: "buffett", weight_pct: 21.43, value_usd: 2, shares: 2, issuer: "APPLE", period_of_report: null },
  ] });
  render(<OwlChips symbol="AAPL" />);
  await waitFor(() => expect(screen.getAllByText(/🦉/)).toHaveLength(2));
  expect(screen.getAllByText(/🦉/)[0].textContent).toContain("buffett · 21.4%");
});

test("renders nothing when the call fails (decoration only)", async () => {
  reply({ error: "boom" }, 502);
  const { container } = render(<OwlChips symbol="AAPL" />);
  await new Promise((r) => setTimeout(r, 20));
  expect(container.textContent).toBe("");
});
