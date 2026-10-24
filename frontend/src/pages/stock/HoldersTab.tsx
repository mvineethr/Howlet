import { useApi } from "../../lib/useApi";
import { api, type Holder } from "../../lib/api";
import { fmtInt, fmtMoney, fmtNum } from "../../lib/fmt";
import Block from "../../blocks/Block";
import DataTable, { type Column } from "../../components/DataTable";
import { FilingsPanel, InsidersPanel } from "./panels";

const num = (s: string) => <span className="num">{s}</span>;

const HOLDER_COLS: Column<Holder>[] = [
  { key: "m", label: "Manager", render: (r) => r.manager },
  { key: "s", label: "Shares", align: "right", render: (r) => num(fmtInt(r.shares)) },
  { key: "v", label: "Value", align: "right", render: (r) => num(fmtMoney(r.value_usd)) },
  { key: "w", label: "Portfolio weight", align: "right", render: (r) => num(`${fmtNum(r.weight_pct, 1)}%`) },
  { key: "p", label: "As of", render: (r) => r.period_of_report ?? "—" },
];

export default function HoldersTab({ symbol }: { symbol: string }) {
  const h = useApi(`holders:${symbol}`, () => api.holders(symbol));
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: 12, alignItems: "start" }}>
      <Block fixed sec title="Tracked superinvestors (13F)" loading={h.loading} error={h.error} fetchedAt={h.fetchedAt}>
        {!h.data && !h.error && <span style={{ color: "var(--dim)" }}>Checking every tracked manager's latest 13F (the first lookup can take a minute)…</span>}
        {h.data && <DataTable columns={HOLDER_COLS} rows={h.data.holders} rowKey={(r) => r.manager + r.issuer}
          empty={`None of the tracked managers (${h.data.tracked_managers.join(", ")}) reported holding ${symbol} in their latest 13F.`} />}
      </Block>
      <InsidersPanel symbol={symbol} />
      <FilingsPanel symbol={symbol} />
    </div>
  );
}
