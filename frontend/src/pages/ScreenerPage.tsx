import { Button, Field, Input } from "@fluentui/react-components";
import { useState } from "react";
import { useApi } from "../lib/useApi";
import { api, type ScreenerRow } from "../lib/api";
import { buildScreenerQuery, type ScreenerInputs } from "../lib/screener";
import { fmtMoney, fmtNum, signed, tone } from "../lib/fmt";
import { downloadCsv } from "../lib/csv";
import { useRoute } from "../lib/route";
import Block from "../blocks/Block";
import DataTable, { tableCsv, type Column } from "../components/DataTable";
import Ticker from "../components/Ticker";

const pct = (n: number | null) => <span className="num" style={{ color: tone(n) }}>{n == null ? "—" : `${signed(n, 1)}%`}</span>;

const COLS: Column<ScreenerRow>[] = [
  { key: "s", label: "Symbol", render: (r) => <Ticker symbol={r.symbol} />, csv: (r) => r.symbol },
  { key: "p", label: "Price", align: "right", render: (r) => <span className="num">{fmtNum(r.price)}</span>, csv: (r) => r.price },
  { key: "c", label: "%Chg", align: "right", render: (r) => pct(r.change_pct), csv: (r) => r.change_pct },
  { key: "m", label: "Mkt cap", align: "right", render: (r) => <span className="num">{fmtMoney(r.market_cap)}</span>, csv: (r) => r.market_cap },
  { key: "pe", label: "P/E", align: "right", render: (r) => <span className="num">{fmtNum(r.pe_ratio, 1)}</span>, csv: (r) => r.pe_ratio },
  { key: "rev", label: "Revenue", align: "right", render: (r) => <span className="num">{fmtMoney(r.revenue)}</span>, csv: (r) => r.revenue },
  { key: "g", label: "Rev growth", align: "right", render: (r) => pct(r.revenue_growth_pct), csv: (r) => r.revenue_growth_pct },
  { key: "nm", label: "Net margin", align: "right", render: (r) => <span className="num">{r.net_margin_pct == null ? "—" : `${fmtNum(r.net_margin_pct, 1)}%`}</span>, csv: (r) => r.net_margin_pct },
];

const LABELS: [keyof ScreenerInputs, string][] = [
  ["peMax", "P/E ≤"], ["mcapMinB", "Market cap ≥ ($B)"], ["growthMin", "Revenue growth ≥ (%)"], ["marginMin", "Net margin ≥ (%)"],
];

export default function ScreenerPage() {
  const [inputs, setInputs] = useState<ScreenerInputs>({ peMax: "", mcapMinB: "", growthMin: "", marginMin: "" });
  const [bad, setBad] = useState<keyof ScreenerInputs | null>(null);
  const [qs, setQs] = useState<string | null>(null);
  const go = useRoute((r) => r.go);
  const res = useApi(qs, () => api.screener(qs ?? ""));

  const run = () => {
    const q = buildScreenerQuery(inputs);
    if ("error" in q) { setBad(q.error); return; }
    setBad(null);
    if (q.qs === qs) res.reload(); else setQs(q.qs);
  };

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
        {LABELS.map(([k, label]) => (
          <Field key={k} label={label} validationMessage={bad === k ? "Enter a number" : undefined} validationState={bad === k ? "error" : "none"}>
            <Input value={inputs[k]} inputMode="decimal" style={{ width: 150 }}
              onChange={(_, d) => setInputs({ ...inputs, [k]: d.value })}
              onKeyDown={(e) => { if (e.key === "Enter") run(); }} />
          </Field>
        ))}
        <Button appearance="primary" onClick={run}>Screen</Button>
      </div>
      {qs !== null && (
        <div style={{ height: "calc(100vh - 210px)" }}>
          <Block fixed sec title={res.data ? `Results · ${res.data.matched} of ${res.data.universe_size} screened` : "Results"}
            loading={res.loading} error={res.error} fetchedAt={res.fetchedAt}
            actions={res.data?.rows.length ? <Button size="small" onClick={() => downloadCsv("screener.csv", tableCsv(COLS, res.data!.rows))}>Export CSV</Button> : undefined}>
            {!res.data && !res.error && <span style={{ color: "var(--dim)" }}>Screening (first run per day is slow — same-day results are cached)…</span>}
            {res.data && <DataTable columns={COLS} rows={res.data.rows} rowKey={(r) => r.symbol}
              empty={`No matches out of ${res.data.universe_size} screened.`}
              onRowClick={(r) => go({ kind: "stock", symbol: r.symbol, tab: "overview" })} />}
          </Block>
        </div>
      )}
    </div>
  );
}
