import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import EconomyTab, { regToNews } from "./EconomyTab";

afterEach(() => vi.restoreAllMocks());
const json = (b: unknown) => Promise.resolve(new Response(JSON.stringify(b)));

test("regToNews keeps the date-only string raw", () => {
  expect(regToNews({ title: "T", type: "Proposed Rule", document_number: "1", html_url: "https://f/1", publication_date: "2026-10-23" }))
    .toEqual({ title: "T", link: "https://f/1", source: "Proposed Rule · 2026-10-23", symbol: null, published: null });
});

test("empty yield curve shows the unavailable text; BLS renders; panels independent", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const u = String(input);
    if (u.startsWith("/api/macro")) return json({ treasury_yield_curve: {}, fred_available: false, fred_series: {},
      bls_series: { cpi: [{ value: "336.940", period: "September", year: "2026" }], unemployment_rate: [], nonfarm_payrolls: [] } });
    if (u.startsWith("/api/regulatory")) return Promise.resolve(new Response("{}", { status: 502 }));
    return json([]);
  });
  render(<FluentProvider theme={webDarkTheme}><EconomyTab /></FluentProvider>);
  await waitFor(() => expect(screen.getByText("Yield curve unavailable right now.")).toBeTruthy());
  expect(screen.getByText("CPI (all items)")).toBeTruthy();
  expect(screen.getByText("336.940")).toBeTruthy();
  expect(screen.getByText("September 2026")).toBeTruthy();
  expect(screen.getByText(/Set FRED_API_KEY/)).toBeTruthy();
  await waitFor(() => expect(screen.getByText("Unavailable, retrying")).toBeTruthy()); // regulatory only
});
