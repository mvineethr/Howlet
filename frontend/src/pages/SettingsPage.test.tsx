import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import SettingsPage from "./SettingsPage";
import { useSettings, DEFAULT_SETTINGS } from "../lib/settings";

beforeEach(() => {
  localStorage.clear(); useSettings.setState({ settings: DEFAULT_SETTINGS });
  vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => {})); // TrackedManagers loads presets; never settle
});
afterEach(() => vi.restoreAllMocks());
const ui = () => render(<FluentProvider theme={webDarkTheme}><SettingsPage /></FluentProvider>);

test("theme mode radio updates the store", () => {
  ui();
  fireEvent.click(screen.getByLabelText("Dark"));
  expect(useSettings.getState().settings.themeMode).toBe("dark");
});

test("hiding a rail page updates railHidden; Home cannot be hidden", () => {
  ui();
  fireEvent.click(screen.getByRole("switch", { name: "Show News" }));
  expect(useSettings.getState().settings.railHidden).toContain("news");
  expect((screen.getByRole("switch", { name: "Show Home" }) as HTMLInputElement).disabled).toBe(true);
});

test("moving a page up reorders the rail", () => {
  ui();
  fireEvent.click(screen.getByRole("button", { name: "Move Markets up" }));
  expect(useSettings.getState().settings.railOrder.slice(0, 2)).toEqual(["markets", "home"]);
});

test("paper reset asks to confirm, then posts the start cash", async () => {
  // Only the reset resolves; other requests (e.g. tracked managers) stay pending as in beforeEach.
  const f = vi.spyOn(globalThis, "fetch").mockImplementation((u) => String(u) === "/api/paper/reset"
    ? Promise.resolve(new Response(JSON.stringify({ account: null, market_open: false })))
    : new Promise<Response>(() => {}));
  ui();
  fireEvent.change(screen.getByLabelText("Paper starting cash"), { target: { value: "5000" } });
  fireEvent.click(screen.getByRole("button", { name: "Reset paper account…" }));
  expect(f.mock.calls.some(([u]) => String(u) === "/api/paper/reset")).toBe(false);
  fireEvent.click(await screen.findByRole("button", { name: "Reset" }));
  await waitFor(() => {
    const post = f.mock.calls.find(([u]) => String(u) === "/api/paper/reset");
    expect(post && JSON.parse(String(post[1]!.body))).toEqual({ start_cash: 5000 });
  });
});
