import { useState } from "react";
import { Button, Caption1, Field, Input } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type RiskPosition } from "../../lib/api";
import { fmtInt, fmtNum, signed, tone } from "../../lib/fmt";
import { loadHoldings, removeHolding, saveHoldings, upsertHolding, type Holding } from "../../lib/holdings";
import Block from "../../blocks/Block";
import DataTable, { type Column } from "../../components/DataTable";
import Ticker from "../../components/Ticker";

const num = (s: string, color?: string) => <span className="num" style={color ? { color } : undefined}>{s}</span>;
const pct = (n: number | null | undefined, signedFmt = false) =>
  n == null ? "—" : `${signedFmt ? signed(n, 1) : fmtNum(n, 1)}%`;

export default function HoldingsTab() {
  const [holdings, setHoldings] = useState<Holding[]>(loadHoldings);
  const [sym, setSym] = useState("");
  const [shares, setShares] = useState("");
  const [err, setErr] = useState("");

  const commit = (next: Holding[]) => { setHoldings(next); saveHoldings(next); };
  const add = () => {
    const r = upsertHolding(holdings, sym, Number(shares));
    if ("error" in r) { setErr(r.error); return; }
    setErr(""); setSym(""); setShares(""); commit(r);
  };

  const risk = useApi(holdings.length ? `risk:${JSON.stringify(holdings)}` : null, () => api.risk(holdings, "1y"));
  const r = risk.data;

  const hCols: Column<Holding>[] = [
    { key: "s", label: "Symbol", render: (h) => <Ticker symbol={h.symbol} /> },
    { key: "n", label: "Shares", align: "right", render: (h) => num(fmtInt(h.shares)) },
    { key: "x", label: "", render: (h) => <Button size="small" appearance="subtle" aria-label={`Remove ${h.symbol}`} onClick={() => commit(removeHolding(holdings, h.symbol))}>✕</Button> },
  ];
  const pCols: Column<RiskPosition>[] = [
    { key: "s", label: "Symbol", render: (p) => <Ticker symbol={p.symbol} /> },
    { key: "w", label: "Weight", align: "right", render: (p) => num(pct(p.weight_pct)) },
    { key: "r", label: "Return", align: "right", render: (p) => num(pct(p.return_pct, true), tone(p.return_pct)) },
    { key: "v", label: "Volatility", align: "right", render: (p) => num(pct(p.annualized_volatility_pct)) },
    { key: "d", label: "Max DD", align: "right", render: (p) => num(pct(p.max_drawdown_pct), tone(p.max_drawdown_pct)) },
  ];
  const stat = (label: string, value: string, color?: string) => (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 24, maxWidth: 360 }}>
      <span style={{ color: "var(--dim)" }}>{label}</span>{num(value, color)}
    </div>
  );

  let riskBody;
  if (!holdings.length) riskBody = <span style={{ color: "var(--dim)" }}>Add positions to compute risk.</span>;
  else if (risk.loading && !r) riskBody = <span style={{ color: "var(--dim)" }}>Fetching price history and computing risk…</span>;
  else if (r?.error && !r.positions?.length) riskBody = <span style={{ color: "var(--dim)" }}>{r.error}</span>;
  else if (r) riskBody = (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {stat("Return (1y)", pct(r.portfolio_return_pct, true), tone(r.portfolio_return_pct))}
      {stat("Annualised volatility", pct(r.portfolio_annualized_volatility_pct))}
      {stat("Max drawdown", pct(r.portfolio_max_drawdown_pct), tone(r.portfolio_max_drawdown_pct))}
      {stat("Sharpe (rf = 0)", fmtNum(r.sharpe_ratio))}
      <DataTable columns={pCols} rows={r.positions} rowKey={(p) => p.symbol} empty="No position data." />
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "flex-start" }}>
        <Field validationMessage={err || undefined} validationState={err ? "error" : "none"}>
          <div style={{ display: "flex", gap: 8 }}>
            <Input aria-label="Symbol" placeholder="Symbol" value={sym} onChange={(_, d) => setSym(d.value)}
              onKeyDown={(e) => { if (e.key === "Enter") add(); }} />
            <Input aria-label="Shares" placeholder="Shares" inputMode="decimal" value={shares} onChange={(_, d) => setShares(d.value)}
              onKeyDown={(e) => { if (e.key === "Enter") add(); }} />
            <Button appearance="primary" onClick={add}>Add / update</Button>
          </div>
        </Field>
      </div>
      <Caption1 style={{ color: "var(--dim)" }}>Saved in this browser — not a 13F filing.</Caption1>
      <Block fixed title="Holdings">
        <DataTable columns={hCols} rows={holdings} rowKey={(h) => h.symbol} empty="No positions yet — add one above." />
      </Block>
      <Block fixed title="Risk" loading={risk.loading} error={risk.error} fetchedAt={risk.fetchedAt}>{riskBody}</Block>
    </div>
  );
}
