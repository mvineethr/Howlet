import { render, screen } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import Block from "./Block";

const wrap = (ui: React.ReactElement) => render(<FluentProvider theme={webDarkTheme}>{ui}</FluentProvider>);

test("error shows even when children are multiple falsy nodes", () => {
  wrap(<Block title="t" error={new Error("boom")} refreshMs={1000}>{false}{undefined}</Block>);
  expect(screen.getByText("Unavailable, retrying")).toBeTruthy();
});

test("sec block shows the error message with falsy children", () => {
  wrap(<Block title="t" sec error={new Error("boom")}>{false}{undefined}</Block>);
  expect(screen.getByText("boom")).toBeTruthy();
});

test("error text says retrying only when the panel refreshes", () => {
  wrap(<Block title="t" error={new Error("boom")} refreshMs={1000} />);
  expect(screen.getByText("Unavailable, retrying")).toBeTruthy();
});

test("error text is plain Unavailable without refreshMs", () => {
  wrap(<Block title="t" error={new Error("boom")} />);
  expect(screen.getByText("Unavailable")).toBeTruthy();
});
