import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import AddBlockDialog from "./AddBlockDialog";

beforeEach(() => { vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(new Response("[]"))); });
afterEach(() => vi.restoreAllMocks());

test("SEC filings needs a symbol; Add sends it upper-cased", async () => {
  const onAdd = vi.fn();
  render(<FluentProvider theme={webDarkTheme}><AddBlockDialog open onClose={() => {}} onAdd={onAdd} /></FluentProvider>);
  fireEvent.click(screen.getByRole("combobox", { name: "Block type" }));
  fireEvent.click(await screen.findByRole("option", { name: "SEC filings" }));
  const add = screen.getByRole("button", { name: "Add" }) as HTMLButtonElement;
  expect(add.disabled).toBe(true);
  fireEvent.change(screen.getByRole("textbox", { name: "Symbol" }), { target: { value: "aapl" } });
  await waitFor(() => expect((screen.getByRole("button", { name: "Add" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  expect(onAdd).toHaveBeenCalledWith("filings", { symbol: "AAPL" });
});
