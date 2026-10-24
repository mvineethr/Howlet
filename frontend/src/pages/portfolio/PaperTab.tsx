import { useState } from "react";
import { Badge, Button, Caption1, Field, Input, Text } from "@fluentui/react-components";
import { api, type PaperOrder, type PaperPosition } from "../../lib/api";
import { useApi } from "../../lib/useApi";
import { fmtNum, signed, tone } from "../../lib/fmt";
import { orderLabel, parseNum, usd } from "../../lib/paper";
import Block from "../../blocks/Block";
import DataTable, { type Column } from "../../components/DataTable";
import Ticker from "../../components/Ticker";
import CompareChart from "../../components/CompareChart";
import OrderTicket from "../../components/OrderTicket";

const num = (s: string, color?: string) => <span className="num" style={color ? { color } : undefined}>{s}</span>;
const pct = (n: number | null | undefined) => (n == null ? "—" : `${signed(n, 1)}%`);
const when = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "—");

export default function PaperTab() {
  const acct = useApi("paper", () => api.paperAccount(), 60_000);
  const hist = useApi("paper-history", () => api.paperHistory(), 10 * 60_000);
  const [ticket, setTicket] = useState(false);
  const [cashText, setCashText] = useState("100000");
  const [msg, setMsg] = useState("");
  const reload = () => { acct.reload(); hist.reload(); };

  const start = async () => {
    const n = parseNum(cashText);
    if (n == null || n <= 0) { setMsg("Starting cash must be more than zero."); return; }
    try { await api.paperReset(n); setMsg(""); reload(); } catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
  };
  const cancel = async (id: string) => {
    try { await api.paperCancel(id); setMsg(""); reload(); } catch (e) { setMsg(e instanceof Error ? e.message : String(e)); }
  };

  const d = acct.data;
  const h = hist.data;
  const header = (
    <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
      <Button appearance="primary" onClick={() => setTicket(true)}>New order</Button>
      {d && <Badge appearance="outline" color={d.market_open ? "success" : "subtle"}>{d.market_open ? "Market open" : "Market closed"}</Badge>}
      <Caption1 style={{ color: "var(--dim)" }}>Fake money — practice only. Prices are delayed up to 15 minutes.</Caption1>
      {msg && <Text role="alert" style={{ color: "var(--down)" }}>{msg}</Text>}
      <OrderTicket open={ticket} onClose={() => setTicket(false)} onPlaced={reload} />
    </div>
  );

  if (d && !d.account) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {header}
        <Block fixed title="Start a paper account">
          <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
            <Field label="Starting cash"><Input inputMode="decimal" value={cashText} onChange={(_, v) => setCashText(v.value)} /></Field>
            <Button appearance="primary" onClick={start}>Start paper account</Button>
          </div>
          <Caption1 style={{ color: "var(--dim)" }}>Or just place an order — a $100,000 account starts automatically.</Caption1>
        </Block>
      </div>
    );
  }

  const posCols: Column<PaperPosition>[] = [
    { key: "s", label: "Symbol", render: (p) => <Ticker symbol={p.symbol} /> },
    { key: "q", label: "Qty", align: "right", render: (p) => num(String(p.qty)) },
    { key: "c", label: "Avg cost", align: "right", render: (p) => num(usd(p.avg_cost)) },
    { key: "p", label: "Price", align: "right", render: (p) => num(usd(p.price)) },
    { key: "v", label: "Value", align: "right", render: (p) => num(usd(p.value)) },
    { key: "u", label: "P/L", align: "right", render: (p) => num(`${usd(p.unrealized)} (${pct(p.unrealized_pct)})`, tone(p.unrealized)) },
  ];
  const openCols: Column<PaperOrder>[] = [
    { key: "o", label: "Order", render: (o) => orderLabel(o) },
    { key: "t", label: "Placed", render: (o) => when(o.ts) },
    { key: "x", label: "", render: (o) => <Button size="small" appearance="subtle" aria-label={`Cancel order ${o.id}`} onClick={() => cancel(o.id)}>Cancel</Button> },
  ];
  const actCols: Column<PaperOrder>[] = [
    { key: "t", label: "When", render: (o) => when(o.fill?.ts ?? o.closed_at) },
    { key: "o", label: "Order", render: (o) => orderLabel(o) },
    { key: "s", label: "Result", render: (o) => (o.status === "filled" ? `Filled at ${usd(o.fill?.price)}` : o.status) },
    { key: "r", label: "Why", render: (o) => o.reason ?? "" },
  ];
  const stat = (label: string, value: string, color?: string) => (
    <div style={{ display: "flex", flexDirection: "column", minWidth: 140 }}>
      <Caption1 style={{ color: "var(--dim)" }}>{label}</Caption1>
      <Text size={500} weight="semibold">{num(value, color)}</Text>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {header}
      <Block fixed title="Account" loading={acct.loading} error={acct.error} fetchedAt={acct.fetchedAt} refreshMs={60_000}>
        {d?.account && (
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            {stat("Account value", usd(d.equity))}
            {stat("Cash", usd(d.cash))}
            {stat("Today", usd(d.day_change), tone(d.day_change))}
            {stat("Total return", pct(d.total_return_pct), tone(d.total_return_pct))}
            {h && h.account_return_pct != null && (
              <Text style={{ alignSelf: "flex-end" }}>{`${pct(h.account_return_pct)} vs S&P 500 ${pct(h.spy_return_pct)}`}</Text>
            )}
            {d.prices_unavailable.length > 0 && <Caption1 style={{ color: "var(--dim)" }}>Prices unavailable: {d.prices_unavailable.join(", ")} (counted at cost)</Caption1>}
          </div>
        )}
      </Block>
      <Block fixed title="Account vs S&P 500" loading={hist.loading} error={hist.error} fetchedAt={hist.fetchedAt}>
        {h && <CompareChart dates={h.dates} a={h.account} b={h.spy} aLabel="Account value" bLabel="S&P 500" />}
      </Block>
      <Block fixed title="Positions">
        {d?.account && <DataTable columns={posCols} rows={d.positions} rowKey={(p) => p.symbol} empty="No positions yet — place an order." />}
      </Block>
      <Block fixed title="Open orders">
        {d?.account && <DataTable columns={openCols} rows={d.open_orders} rowKey={(o) => o.id} empty="No open orders." />}
      </Block>
      <Block fixed title="Activity">
        {d?.account && <DataTable columns={actCols} rows={d.activity} rowKey={(o) => o.id} empty="Nothing yet." />}
      </Block>
      <Caption1 style={{ color: "var(--dim)" }}>Realised P/L so far: {d?.account ? usd(d.realized_pnl) : "—"} · started with {d?.account ? usd(d.account.start_cash) : "—"} · {fmtNum(d?.account ? d.positions.length : 0, 0)} positions</Caption1>
    </div>
  );
}
