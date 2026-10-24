import { addSymbol, createList, deleteList, removeSymbol, saveWatchlists, WATCHLISTS_KEY } from "./watchlists";

beforeEach(() => localStorage.clear());

test("add/remove normalise, dedupe and never mutate", () => {
  const all = { default: ["AAPL"] };
  const a = addSymbol(all, "default", " msft ");
  expect(a.default).toEqual(["AAPL", "MSFT"]);
  expect(all.default).toEqual(["AAPL"]);
  expect(addSymbol(a, "default", "aapl")).toBe(a);
  expect(addSymbol(a, "default", "  ")).toBe(a);
  expect(removeSymbol(a, "default", "AAPL").default).toEqual(["MSFT"]);
});

test("create and delete lists", () => {
  const r = createList({ default: [] }, " Tech ");
  expect(r).toEqual({ all: { default: [], tech: [] }, name: "tech" });
  expect(createList({ default: [] }, "DEFAULT")).toEqual({ error: "That list already exists." });
  expect(createList({ default: [] }, " ")).toEqual({ error: "Name the list." });
  expect(deleteList({ default: [], tech: [] }, "tech")).toEqual({ default: [] });
  const only = { default: ["A"] };
  expect(deleteList(only, "default")).toBe(only);
});

test("save writes the classic shape", () => {
  saveWatchlists({ default: ["AAPL"] });
  expect(JSON.parse(localStorage.getItem(WATCHLISTS_KEY)!)).toEqual({ default: ["AAPL"] });
});
