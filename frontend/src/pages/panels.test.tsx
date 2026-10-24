import { fireEvent, render, screen } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import { FedPanel } from "./markets/panels";
import { FilingsPanel } from "./stock/panels";
import { InsiderBuysPanel } from "./smart/panels";

afterEach(() => vi.restoreAllMocks());

test("a panel with onRemove shows a remove button and calls it; without, none", () => {
  vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => {}));
  const onRemove = vi.fn();
  const { unmount } = render(<FluentProvider theme={webDarkTheme}><FedPanel limit={10} onRemove={onRemove} /></FluentProvider>);
  fireEvent.click(screen.getByRole("button", { name: /Remove/ }));
  expect(onRemove).toHaveBeenCalled();
  unmount();
  render(<FluentProvider theme={webDarkTheme}><FedPanel limit={10} /></FluentProvider>);
  expect(screen.queryByRole("button", { name: /Remove/ })).toBeNull();
});

test("panels accept a title that shows their subject", () => {
  vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => {}));
  render(<FluentProvider theme={webDarkTheme}><FilingsPanel symbol="AAPL" title="SEC filings · AAPL" onRemove={() => {}} /></FluentProvider>);
  expect(screen.getByText("SEC filings · AAPL")).toBeTruthy();
});

test("insider-buys panel on an empty list still has a remove button", () => {
  const onRemove = vi.fn();
  render(<FluentProvider theme={webDarkTheme}><InsiderBuysPanel list={[]} onRemove={onRemove} /></FluentProvider>);
  fireEvent.click(screen.getByRole("button", { name: /Remove/ }));
  expect(onRemove).toHaveBeenCalled();
});
