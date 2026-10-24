import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import ManagerPicker from "./ManagerPicker";

afterEach(() => vi.restoreAllMocks());

test("typing a prefix then Enter commits exactly once", async () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
    Promise.resolve(new Response(JSON.stringify([{ label: "ackman", cik: "1" }, { label: "buffett", cik: "2" }]))));
  const onPick = vi.fn();
  render(<FluentProvider theme={webDarkTheme}><ManagerPicker value="" onPick={onPick} /></FluentProvider>);
  await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
  const input = screen.getByRole("combobox", { name: "Manager or CIK" });
  fireEvent.change(input, { target: { value: "ack" } });
  fireEvent.keyDown(input, { key: "Enter" });
  expect(onPick).toHaveBeenCalledTimes(1);
});
