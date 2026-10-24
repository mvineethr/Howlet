import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import ScreenerPage from "./ScreenerPage";

afterEach(() => vi.restoreAllMocks());

test("a failed screen shows the server's error text", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: "boom" }), { status: 502 }));
  render(<FluentProvider theme={webDarkTheme}><ScreenerPage /></FluentProvider>);
  fireEvent.click(screen.getByText("Screen"));
  await waitFor(() => expect(screen.getByText("boom")).toBeTruthy());
});
