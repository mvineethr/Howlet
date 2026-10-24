import { fireEvent, render, screen } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import LayoutsMenu from "./LayoutsMenu";
import { SNAPSHOTS_KEY } from "../../lib/homeState";

beforeEach(() => localStorage.clear());

test("deleting a saved layout asks for confirmation first", async () => {
  const snap = { tabs: [{ id: "t", name: "T", blocks: [] }], active: "t" };
  localStorage.setItem(SNAPSHOTS_KEY, JSON.stringify({ mine: snap }));
  render(<FluentProvider theme={webDarkTheme}><LayoutsMenu home={snap} save={() => {}} /></FluentProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Layouts" }));
  fireEvent.click(await screen.findByRole("menuitem", { name: "Delete" }));
  fireEvent.click(await screen.findByRole("menuitem", { name: "mine" }));
  expect(await screen.findByText('Delete saved layout "mine"?')).toBeTruthy();
  expect(localStorage.getItem(SNAPSHOTS_KEY)).toContain("mine");
  fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
  expect(localStorage.getItem(SNAPSHOTS_KEY)).not.toContain("mine");
});
