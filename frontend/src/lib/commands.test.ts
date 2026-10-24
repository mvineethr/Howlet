import { parseCommand } from "./commands";

const M = ["buffett", "ackman"];

test.each([
  ["AAPL", { kind: "go", route: { kind: "stock", symbol: "AAPL", tab: "overview" } }],
  ["aapl des", { kind: "go", route: { kind: "stock", symbol: "AAPL", tab: "overview" } }],
  ["AAPL GP", { kind: "go", route: { kind: "stock", symbol: "AAPL", tab: "chart" } }],
  ["AAPL FA", { kind: "go", route: { kind: "stock", symbol: "AAPL", tab: "financials" } }],
  ["AAPL HDS", { kind: "go", route: { kind: "stock", symbol: "AAPL", tab: "holders" } }],
  ["AAPL OPT", { kind: "go", route: { kind: "stock", symbol: "AAPL", tab: "options" } }],
  ["news", { kind: "go", route: { kind: "page", page: "news" } }],
  ["MKTS", { kind: "go", route: { kind: "page", page: "markets" } }],
  ["ECO", { kind: "go", route: { kind: "page", page: "markets" } }],
  ["EQS", { kind: "go", route: { kind: "page", page: "screener" } }],
  ["W", { kind: "go", route: { kind: "page", page: "portfolio" } }],
  ["PF", { kind: "go", route: { kind: "page", page: "portfolio" } }],
  ["home", { kind: "go", route: { kind: "page", page: "home" } }],
  ["buffett", { kind: "manager", id: "buffett" }],
  ["ackman port", { kind: "manager", id: "ackman" }],
  ["1067983", { kind: "manager", id: "1067983" }],
  ["alert tsla < 200", { kind: "alert", symbol: "TSLA", op: "<", price: 200 }],
  ["ALERT BRK-B > 532.5", { kind: "alert", symbol: "BRK-B", op: ">", price: 532.5 }],
])("%s", (input, expected) => {
  expect(parseCommand(input, M)).toEqual(expected);
});

test("bad alert syntax explains itself", () => {
  expect(parseCommand("alert tsla", M)).toEqual({ kind: "error", message: "Usage: ALERT AAPL > 350" });
});

test("empty input is null", () => {
  expect(parseCommand("   ", M)).toBeNull();
});

test.each(["help", "?", "about", "FAQ"])("%s opens the help page", (c) => {
  expect(parseCommand(c, M)).toEqual({ kind: "go", route: { kind: "page", page: "settings", params: ["help"] } });
});

test("PAPER opens the Paper tab", () => {
  expect(parseCommand("paper", [])).toEqual({ kind: "go", route: { kind: "page", page: "portfolio", params: ["paper"] } });
});
