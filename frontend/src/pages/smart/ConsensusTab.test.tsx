import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import ConsensusTab from "./ConsensusTab";
import { resolveSmartTab } from "../SmartMoneyPage";

afterEach(() => vi.restoreAllMocks());

test("resolveSmartTab: param, then saved, then managers", () => {
  expect(resolveSmartTab(["funds"], "consensus")).toBe("funds");
  expect(resolveSmartTab(["bogus"], "consensus")).toBe("consensus");
  expect(resolveSmartTab([], null)).toBe("managers");
});

test("consensus rows show held-by counts and manager names", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    managers: [{ label: "buffett", period_of_report: "2026-06-30" }, { label: "ackman", period_of_report: "2026-03-31" }, { label: "loeb", period_of_report: null }],
    rows: [{ issuer: "ALPHABET INC", cusip: "02079K305", manager_count: 2, total_value_usd: 5e9, combined_weight_pct: 12.34,
      weights_pct: { buffett: 2.1, ackman: 10.24 } }],
  })));
  render(<FluentProvider theme={webDarkTheme}><ConsensusTab /></FluentProvider>);
  await waitFor(() => expect(screen.getByText("ALPHABET INC")).toBeTruthy());
  expect(screen.getByText("2 of 3")).toBeTruthy();
  expect(screen.getByText("buffett, ackman")).toBeTruthy();
  expect(screen.getByText("$5.00B")).toBeTruthy();
  expect(screen.getByText("Consensus across 3 managers")).toBeTruthy();
});
