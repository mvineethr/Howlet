import { render, screen, fireEvent } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import SettingsPage from "./SettingsPage";
import { useSettings, DEFAULT_SETTINGS } from "../lib/settings";

beforeEach(() => { localStorage.clear(); useSettings.setState({ settings: DEFAULT_SETTINGS }); });
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
