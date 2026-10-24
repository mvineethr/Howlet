import { fireEvent, render, screen } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import { FedPanel } from "./markets/panels";

afterEach(() => vi.restoreAllMocks());

test("a panel with onRemove shows a remove button and calls it; without, none", () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]"));
  const onRemove = vi.fn();
  const { unmount } = render(<FluentProvider theme={webDarkTheme}><FedPanel limit={10} onRemove={onRemove} /></FluentProvider>);
  fireEvent.click(screen.getByRole("button", { name: /Remove/ }));
  expect(onRemove).toHaveBeenCalled();
  unmount();
  render(<FluentProvider theme={webDarkTheme}><FedPanel limit={10} /></FluentProvider>);
  expect(screen.queryByRole("button", { name: /Remove/ })).toBeNull();
});
