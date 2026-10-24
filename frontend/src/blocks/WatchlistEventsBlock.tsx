import { getWatchlists } from "../lib/legacy";
import { useSequentialEvents } from "../lib/events";
import type { Events } from "../lib/api";
import { stockSymbols } from "../pages/smart/InsiderBuysTab";
import DataTable, { type Column } from "../components/DataTable";
import Ticker from "../components/Ticker";
import Block from "./Block";

const dim = <span style={{ color: "var(--dim)" }}>unavailable</span>;
const COLS: Column<{ s: string; e: Events | "error" | undefined }>[] = [
  { key: "s", label: "Symbol", render: (r) => <Ticker symbol={r.s} /> },
  { key: "e", label: "Next earnings", render: (r) => r.e === "error" ? dim : <span className="num">{r.e?.next_earnings_date ?? "—"}</span> },
  { key: "a", label: "Analysts", render: (r) => r.e === "error" ? null : <span className="num">{r.e?.analyst_recommendation ?? "—"}</span> },
];

export default function WatchlistEventsBlock({ list = "default", onRemove }: { list?: string; onRemove?: () => void }) {
  const syms = stockSymbols(getWatchlists()[list] ?? []).slice(0, 8);
  const events = useSequentialEvents(syms);
  const rows = syms.flatMap((s) => (events.has(s) ? [{ s, e: events.get(s) }] : []));
  return (
    <Block title={`Watchlist events · ${list}`} {...{ onRemove }}>
      <DataTable columns={COLS} rows={rows} rowKey={(r) => r.s} empty={syms.length ? "Loading events…" : "No stock symbols in this list."} />
    </Block>
  );
}
