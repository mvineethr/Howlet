import { Link } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type Filing, type Holder, type InsiderTxn } from "../../lib/api";
import { fmtInt, fmtMoney, fmtNum, safeHref } from "../../lib/fmt";
import Block from "../../blocks/Block";
import DataTable, { type Column } from "../../components/DataTable";

const FIVE_MIN = 300_000;
const num = (s: string) => <span className="num">{s}</span>;

const HOLDER_COLS: Column<Holder>[] = [
  { key: "m", label: "Manager", render: (r) => r.manager },
  { key: "s", label: "Shares", align: "right", render: (r) => num(fmtInt(r.shares)) },
  { key: "v", label: "Value", align: "right", render: (r) => num(fmtMoney(r.value_usd)) },
  { key: "w", label: "Portfolio weight", align: "right", render: (r) => num(`${fmtNum(r.weight_pct, 1)}%`) },
  { key: "p", label: "As of", render: (r) => r.period_of_report ?? "—" },
];

const codeColor = (c: string) => (c === "P" ? "var(--up)" : c === "S" ? "var(--down)" : "var(--dim)");
const TXN_COLS: Column<InsiderTxn>[] = [
  { key: "d", label: "Date", render: (r) => r.date ?? "?" },
  { key: "i", label: "Insider", render: (r) => <span title={r.relationship ?? undefined}>{r.insider}</span> },
  { key: "t", label: "Type", render: (r) => <span style={{ color: codeColor(r.code) }}>{r.code_label}</span> },
  { key: "s", label: "Shares", align: "right", render: (r) => num(fmtInt(r.shares)) },
  { key: "p", label: "Price", align: "right", render: (r) => num(fmtNum(r.price_per_share)) },
  { key: "v", label: "Value", align: "right", render: (r) => num(fmtMoney(r.value_usd)) },
];

const FILING_COLS: Column<Filing>[] = [
  { key: "d", label: "Filed", render: (r) => r.filing_date },
  { key: "f", label: "Form", render: (r) => <Link href={safeHref(r.url)} target="_blank" rel="noopener noreferrer">{r.form ?? "?"}</Link> },
  { key: "p", label: "Period", render: (r) => r.period_of_report ?? "—" },
];

export default function HoldersTab({ symbol }: { symbol: string }) {
  const h = useApi(`holders:${symbol}`, () => api.holders(symbol));
  const ins = useApi(`insiders:${symbol}`, () => api.insiders(symbol, 15), FIVE_MIN);
  const fil = useApi(`filings:${symbol}`, () => api.filings(symbol, 15), FIVE_MIN);
  const s = ins.data?.summary;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: 12, alignItems: "start" }}>
      <Block fixed sec title="Tracked superinvestors (13F)" loading={h.loading} error={h.error} fetchedAt={h.fetchedAt}>
        {!h.data && !h.error && <span style={{ color: "var(--dim)" }}>Checking every tracked manager's latest 13F (the first lookup can take a minute)…</span>}
        {h.data && <DataTable columns={HOLDER_COLS} rows={h.data.holders} rowKey={(r) => r.manager + r.issuer}
          empty={`None of the tracked managers (${h.data.tracked_managers.join(", ")}) reported holding ${symbol} in their latest 13F.`} />}
      </Block>
      <Block fixed sec title="Insider transactions (Form 4)" loading={ins.loading} error={ins.error} fetchedAt={ins.fetchedAt} refreshMs={FIVE_MIN}>
        {ins.data && s && (
          <>
            <div style={{ color: "var(--dim)", marginBottom: 6 }}>
              {`last ${ins.data.filings_scanned} Form 4s · ${s.open_market_purchases} buys ${fmtMoney(s.purchase_value_usd)} · ${s.open_market_sales} sells ${fmtMoney(s.sale_value_usd)}`}
            </div>
            <DataTable columns={TXN_COLS} rows={ins.data.transactions.slice(0, 20)} rowKey={(r) => `${r.accession_number}-${r.insider}-${r.date}-${r.shares}`}
              empty="No non-derivative insider transactions in these filings." />
          </>
        )}
      </Block>
      <Block fixed sec title="SEC filings" loading={fil.loading} error={fil.error} fetchedAt={fil.fetchedAt} refreshMs={FIVE_MIN}>
        {fil.data && <DataTable columns={FILING_COLS} rows={fil.data.filings} rowKey={(r) => r.accession_number} empty="No recent SEC filings." />}
      </Block>
    </div>
  );
}
