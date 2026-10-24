import { render, screen, fireEvent } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import HelpPage from "./HelpPage";
import { BLOCKS } from "../blocks/registry";

const scroll = vi.fn();
beforeEach(() => { scroll.mockClear(); Element.prototype.scrollIntoView = scroll; });
const ui = () => render(<FluentProvider theme={webDarkTheme}><HelpPage /></FluentProvider>);

const SECTIONS = ["About", "Glossary", "Commands", "Pages", "Blocks", "Charting", "FAQ", "Tips", "Plug this into your AI", "Sources"];

test("renders every section heading", () => {
  ui();
  for (const s of SECTIONS) expect(screen.getByRole("heading", { name: s })).toBeTruthy();
});

test("every jump button scrolls its section into view", () => {
  ui();
  const buttons = screen.getByRole("navigation", { name: "Help sections" }).querySelectorAll("button");
  expect(buttons.length).toBe(SECTIONS.length);
  buttons.forEach((b) => fireEvent.click(b));
  expect(scroll).toHaveBeenCalledTimes(SECTIONS.length);
});

test("lists all block types", () => {
  ui();
  for (const b of Object.values(BLOCKS)) expect(screen.getAllByText(b.label).length).toBeGreaterThan(0);
});
