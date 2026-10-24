import { Button } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type FiscalYear } from "../../lib/api";
import { fmtMoney, fmtNum, tone } from "../../lib/fmt";
import { downloadCsv } from "../../lib/csv";
import Block from "../../blocks/Block";
import DataTable, { tableCsv, type Column } from "../../components/DataTable";

const money = (k: keyof FiscalYear, label: string, toned = false): Column<FiscalYear> => ({
  key: k, label, align: "right",
  render: (r) => <span className="num" style={toned ? { color: tone(r[k] as number | null) } : undefined}>{fmtMoney(r[k] as number | null)}</span>,
  csv: (r) => r[k] as number | null,
});

const COLS: Column<FiscalYear>[] = [
  { key: "fy", label: "Fiscal year", render: (r) => <><b>{`FY${r.fiscal_year}`}</b> <span style={{ color: "var(--dim)" }}>{r.end_date}</span></>, csv: (r) => `FY${r.fiscal_year} ${r.end_date}` },
  money("revenue", "Revenue"),
  money("net_income", "Net income", true),
  { key: "eps", label: "EPS (diluted)", align: "right", render: (r) => <span className="num">{fmtNum(r.eps_diluted)}</span>, csv: (r) => r.eps_diluted },
  money("total_assets", "Total assets"),
  money("total_liabilities", "Total liabilities"),
  money("stockholders_equity", "Equity"),
  money("operating_cash_flow", "Operating cash flow"),
];

export default function FinancialsTab({ symbol }: { symbol: string }) {
  const { data, error, loading, fetchedAt } = useApi(`facts:${symbol}`, () => api.facts(symbol));
  return (
    <Block fixed sec title={data ? `Annual financials · ${data.company}` : "Annual financials"} loading={loading} error={error} fetchedAt={fetchedAt}
      actions={data?.fiscal_years.length ? <Button size="small" onClick={() => downloadCsv(`${symbol}-financials.csv`, tableCsv(COLS, data.fiscal_years))}>Export CSV</Button> : undefined}>
      {data && <DataTable columns={COLS} rows={data.fiscal_years} rowKey={(r) => String(r.fiscal_year)}
        empty="No annual XBRL facts (fund, foreign issuer, or non-10-K filer)." />}
    </Block>
  );
}
