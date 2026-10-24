import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import NewsPage from "./NewsPage";

afterEach(() => vi.restoreAllMocks());

test("wire, earnings filter and fed panel load independently", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.startsWith("/api/fed-events")) return Promise.resolve(new Response("{}", { status: 502 }));
    return Promise.resolve(new Response(JSON.stringify([
      { title: "Wire story", link: "https://a/1", source: "Yahoo Finance", symbol: null, published: null },
      { title: "Beat and raise", link: "https://a/2", source: "CNBC Earnings", symbol: null, published: null },
    ])));
  });
  render(<FluentProvider theme={webDarkTheme}><NewsPage /></FluentProvider>);
  await waitFor(() => expect(screen.getAllByText("Beat and raise")).toHaveLength(2)); // wire + earnings
  expect(screen.getByText("Wire story")).toBeTruthy();
  await waitFor(() => expect(screen.getByText("Unavailable, retrying")).toBeTruthy()); // fed failed quietly
});
