type Cell = string | number | null | undefined;

const cell = (v: Cell): string => {
  const s0 = v == null ? "" : String(v);
  const s = typeof v === "string" && /^[=+\-@\t\r]/.test(v) ? `'${s0}` : s0; // formula-injection guard
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export const toCsv = (header: string[], rows: Cell[][]): string =>
  [header, ...rows].map((r) => r.map(cell).join(",")).join("\r\n");

export function downloadCsv(filename: string, csv: string): void {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
