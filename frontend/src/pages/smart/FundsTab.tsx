import { useState } from "react";
import { Button, Caption1, Input } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type FundHolding } from "../../lib/api";
import { fmtMoney, fmtNum } from "../../lib/fmt";
import { downloadCsv } from "../../lib/csv";
import { useRoute } from "../../lib/route";
import Block from "../../blocks/Block";
import DataTable, { tableCsv, type Column } from "../../components/DataTable";

const cols: Column<FundHolding>[] = [
  { key: "n", label: "Holding", render: (r) => <span title={r.title ?? undefined}>{r.name}</span>, csv: (r) => r.name },
  { key: "v", label: "Value", align: "right", render: (r) => <span className="num">{fmtMoney(r.value_usd)}</span>, csv: (r) => r.value_usd },
  { key: "p", label: "% of fund", align: "right", render: (r) => <span className="num">{`${fmtNum(r.pct_val, 2)}%`}</span>, csv: (r) => r.pct_val },
  { key: "a", label: "Asset", render: (r) => r.asset_cat ?? "—", csv: (r) => r.asset_cat },
  { key: "c", label: "Country", render: (r) => r.country ?? "—", csv: (r) => r.country },
];

export default function FundsTab({ symbol }: { symbol: string }) {
  const go = useRoute((r) => r.go);
  const [text, setText] = useState(symbol);
  const run = () => { const s = text.trim().toUpperCase(); if (s) go({ kind: "page", page: "smart", params: ["funds", s] }); };
  const { data, loading, error, fetchedAt } = useApi(symbol ? `fund:${symbol}` : null, () => api.fund(symbol, 50));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <Input size="small" placeholder="ETF or mutual fund ticker" aria-label="Fund ticker" value={text} onChange={(_, d) => setText(d.value)} onKeyDown={(e) => { if (e.key === "Enter") run(); }} />
        <Button size="small" appearance="primary" onClick={run}>Load</Button>
      </div>
      <Caption1 style={{ color: "var(--dim)" }}>Funds report holdings monthly on SEC Form N-PORT. Unit investment trusts such as SPY don't file it.</Caption1>
      {symbol && (
        <Block fixed sec title={data?.fund || "Fund holdings"} loading={loading} error={error} fetchedAt={fetchedAt}
          actions={data?.holdings.length ? <Button size="small" onClick={() => downloadCsv(`${symbol}-holdings.csv`, tableCsv(cols, data.holdings))}>Export CSV</Button> : undefined}>
          {data && (
            <>
              <Caption1 style={{ color: "var(--dim)" }}>{`as of ${data.report_period_date ?? "?"} · net assets ${fmtMoney(data.net_assets)} · ${data.position_count} positions`}</Caption1>
              <DataTable columns={cols} rows={data.holdings} rowKey={(r, i) => `${r.cusip ?? r.name}:${i}`} empty="No holdings reported." />
            </>
          )}
        </Block>
      )}
    </div>
  );
}
