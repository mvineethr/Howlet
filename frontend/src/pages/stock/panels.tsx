import { Link } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type Filing, type InsiderTxn } from "../../lib/api";
import { fmtInt, fmtMoney, fmtNum, safeHref } from "../../lib/fmt";
import Block from "../../blocks/Block";
import DataTable, { type Column } from "../../components/DataTable";

const FIVE_MIN = 300_000;
const num = (s: string) => <span className="num">{s}</span>;

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

type P = { symbol: string; onRemove?: () => void };

export function InsidersPanel({ symbol, onRemove }: P) {
  const ins = useApi(`insiders:${symbol}`, () => api.insiders(symbol, 15), FIVE_MIN);
  const s = ins.data?.summary;
  return (
    <Block fixed={!onRemove} onRemove={onRemove} sec title="Insider transactions (Form 4)" loading={ins.loading} error={ins.error} fetchedAt={ins.fetchedAt} refreshMs={FIVE_MIN}>
      {ins.data && s && (
        <>
          <div style={{ color: "var(--dim)", marginBottom: 6 }}>
            {`last ${ins.data.filings_scanned} Form 4s · ${s.open_market_purchases} buys ${fmtMoney(s.purchase_value_usd)} · ${s.open_market_sales} sells ${fmtMoney(s.sale_value_usd)}`}
          </div>
          <DataTable columns={TXN_COLS} rows={ins.data.transactions.slice(0, 20)} rowKey={(r, i) => `${r.accession_number}-${i}`}
            empty="No non-derivative insider transactions in these filings." />
        </>
      )}
    </Block>
  );
}

export function FilingsPanel({ symbol, onRemove }: P) {
  const fil = useApi(`filings:${symbol}`, () => api.filings(symbol, 15), FIVE_MIN);
  return (
    <Block fixed={!onRemove} onRemove={onRemove} sec title="SEC filings" loading={fil.loading} error={fil.error} fetchedAt={fil.fetchedAt} refreshMs={FIVE_MIN}>
      {fil.data && <DataTable columns={FILING_COLS} rows={fil.data.filings} rowKey={(r) => r.accession_number} empty="No recent SEC filings." />}
    </Block>
  );
}
