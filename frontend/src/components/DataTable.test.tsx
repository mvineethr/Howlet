import { fireEvent, render, screen } from "@testing-library/react";
import DataTable, { tableCsv, type Column } from "./DataTable";

type R = { s: string; v: number };
const cols: Column<R>[] = [
  { key: "s", label: "SYM", render: (r) => r.s, csv: (r) => r.s },
  { key: "v", label: "VAL", align: "right", render: (r) => r.v.toFixed(1), csv: (r) => r.v },
];

test("renders headers, rows, and row clicks", () => {
  const click = vi.fn();
  render(<DataTable columns={cols} rows={[{ s: "A", v: 1 }, { s: "B", v: 2 }]} rowKey={(r) => r.s} empty="none" onRowClick={click} />);
  expect(screen.getByText("SYM")).toBeTruthy();
  fireEvent.click(screen.getByText("B"));
  expect(click).toHaveBeenCalledWith({ s: "B", v: 2 });
});

test("empty rows show the empty text", () => {
  render(<DataTable columns={cols} rows={[]} rowKey={(r) => r.s} empty="Nothing here." />);
  expect(screen.getByText("Nothing here.")).toBeTruthy();
});

test("tableCsv uses labels and csv accessors", () => {
  expect(tableCsv(cols, [{ s: "A", v: 1.5 }])).toBe("SYM,VAL\r\nA,1.5");
});
