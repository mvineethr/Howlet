import type { ReactNode } from "react";
import { toCsv } from "../lib/csv";

export type Column<T> = {
  key: string; label: string; align?: "left" | "right";
  render: (r: T) => ReactNode; csv?: (r: T) => string | number | null;
};

type Props<T> = { columns: Column<T>[]; rows: T[]; rowKey: (r: T, i: number) => string; empty: string; onRowClick?: (r: T) => void };

export default function DataTable<T>({ columns, rows, rowKey, empty, onRowClick }: Props<T>) {
  if (!rows.length) return <div style={{ color: "var(--dim)", padding: "4px 0" }}>{empty}</div>;
  return (
    <table className="dt">
      <thead>
        <tr>{columns.map((c) => <th key={c.key} style={{ textAlign: c.align ?? "left" }}>{c.label}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={rowKey(r, i)} onClick={onRowClick ? () => onRowClick(r) : undefined} style={onRowClick ? { cursor: "pointer" } : undefined}>
            {columns.map((c) => <td key={c.key} style={{ textAlign: c.align ?? "left" }}>{c.render(r)}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export const tableCsv = <T,>(columns: Column<T>[], rows: T[]): string =>
  toCsv(columns.map((c) => c.label), rows.map((r) => columns.map((c) => (c.csv ? c.csv(r) : ""))));
