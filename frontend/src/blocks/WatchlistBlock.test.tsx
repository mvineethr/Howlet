import { render, screen } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import WatchlistBlock from "./WatchlistBlock";

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

test("an empty list shows a hint and makes no request", () => {
  localStorage.setItem("howlet_watchlists_v1", JSON.stringify({ default: ["AAPL"], empty: [] }));
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  render(<FluentProvider theme={webDarkTheme}><WatchlistBlock list="empty" /></FluentProvider>);
  expect(screen.getByText(/Empty list/)).toBeTruthy();
  expect(fetchSpy).not.toHaveBeenCalled();
});
