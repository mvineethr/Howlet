import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import FilingSearchTab, { parseForms } from "./FilingSearchTab";

afterEach(() => vi.restoreAllMocks());

test("parseForms normalises the forms list", () => {
  expect(parseForms(" 10-k, 8-K  def 14a")).toEqual(["10-K", "8-K", "DEF", "14A"]);
  expect(parseForms("")).toEqual([]);
});

test("results render with safe document links and raw dates", async () => {
  const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ query: "x", forms: ["8-K"], results: [
    { accession_number: "a", cik: "1", company: "ACME CORP", file_date: "2025-03-01", file_description: "Press release", file_type: "EX-99", form: "8-K", url: "https://www.sec.gov/x.htm" },
    { accession_number: "b", cik: "2", company: "EVIL INC", file_date: "2025-03-02", file_description: null, file_type: "EX-1", form: "8-K", url: "javascript:alert(1)" },
  ] })));
  render(<FluentProvider theme={webDarkTheme}><FilingSearchTab query="share repurchase" forms="8-K" /></FluentProvider>);
  await waitFor(() => expect(screen.getByText("ACME CORP")).toBeTruthy());
  expect(String(f.mock.calls[0][0])).toContain("forms=8-K");
  expect(screen.getByText("2025-03-01")).toBeTruthy();
  expect(screen.getByText("Press release").closest("a")?.getAttribute("href")).toBe("https://www.sec.gov/x.htm");
  expect(screen.getByText("EX-1").closest("a")?.getAttribute("href") ?? null).toBeNull(); // Fluent Link w/o href renders a <button>
});
