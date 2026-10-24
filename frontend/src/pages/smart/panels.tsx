import type { CSSProperties } from "react";
import { Button, Caption1 } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type ConsensusRow, type FundHolding, type InsiderBuy, type PortfolioPosition } from "../../lib/api";
import { fmtInt, fmtMoney, fmtNum, signed, tone } from "../../lib/fmt";
import { downloadCsv } from "../../lib/csv";
import Block from "../../blocks/Block";
import DataTable, { tableCsv, type Column } from "../../components/DataTable";
import Ticker from "../../components/Ticker";
import Sparkline from "../../components/Sparkline";

type P = { onRemove?: () => void };
const num = (s: string, style?: CSSProperties) => <span className="num" style={style}>{s}</span>;

const HOLD_COLS: Column<PortfolioPosition & { i: number }>[] = [
  { key: "n", label: "#", render: (r) => <span style={{ color: "var(--dim)" }}>{r.i + 1}</span>, csv: (r) => r.i + 1 },
  { key: "t", label: "Ticker", render: (r) => <Ticker symbol={r.ticker} />, csv: (r) => r.ticker },
  { key: "is", label: "Issuer", render: (r) => r.issuer, csv: (r) => r.issuer },
  { key: "p", label: "Price", align: "right", render: (r) => num(fmtNum(r.price)), csv: (r) => r.price },
  { key: "c", label: "%Chg", align: "right", render: (r) => num(r.change_pct == null ? "—" : `${signed(r.change_pct)}%`, { color: tone(r.change_pct) }), csv: (r) => r.change_pct },
  { key: "s", label: "1M", render: (r) => <Sparkline values={r.sparkline} w={70} h={16} /> },
  { key: "v", label: "Value", align: "right", render: (r) => num(fmtMoney(r.value_usd)), csv: (r) => r.value_usd },
  { key: "sh", label: "Shares", align: "right", render: (r) => num(fmtInt(r.shares), { color: "var(--dim)" }), csv: (r) => r.shares },
  { key: "w", label: "Weight", align: "right", render: (r) => num(`${fmtNum(r.weight_pct, 1)}%`), csv: (r) => r.weight_pct },
];
const COMPACT_KEYS = new Set(["p", "s", "sh"]);

export function HoldingsPanel({ manager, top = 25, compact = false, onRemove }: P & { manager: string; top?: number; compact?: boolean }) {
  const port = useApi(`portfolio:${manager}:${top}`, () => api.portfolio(manager, top));
  const rows = (port.data?.positions ?? []).map((p, i) => ({ ...p, i }));
  const d = port.data;
  const cols = compact ? HOLD_COLS.filter((c) => !COMPACT_KEYS.has(c.key)) : HOLD_COLS;
  return (
    <Block fixed={!onRemove} onRemove={onRemove} sec title={`Holdings · ${manager}`} loading={port.loading} error={port.error} fetchedAt={port.fetchedAt}
      actions={rows.length && !compact ? <Button size="small" onClick={() => downloadCsv(`${manager}-portfolio.csv`, tableCsv(HOLD_COLS, rows))}>Export CSV</Button> : undefined}>
      {!d && !port.error && <span style={{ color: "var(--dim)" }}>Loading the latest 13F (the first load of a manager maps tickers and can take ~30s)…</span>}
      {d && (
        <>
          <Caption1 style={{ color: "var(--dim)" }}>{`CIK ${d.cik} · period ${d.period_of_report ?? "?"} · filed ${d.filing_date ?? "?"} · ${d.position_count} positions · ${fmtMoney(d.total_value_usd)}`}</Caption1>
          <DataTable columns={cols} rows={rows} rowKey={(r) => r.cusip} empty="No positions." />
        </>
      )}
    </Block>
  );
}

export function ConsensusPanel({ min = 2, limit = 25, onRemove }: P & { min?: number; limit?: number }) {
  const { data, error, loading, fetchedAt } = useApi(`consensus:${min}:${limit}`, () => api.consensus(min, limit));
  const n = data?.managers.length ?? 0;
  const cols: Column<ConsensusRow>[] = [
    { key: "i", label: "Issuer", render: (r) => r.issuer, csv: (r) => r.issuer },
    { key: "h", label: "Held by", align: "right", render: (r) => <span className="num" style={{ color: "var(--up)" }}>{`${r.manager_count} of ${n}`}</span>, csv: (r) => r.manager_count },
    { key: "m", label: "Managers", render: (r) => <span title={Object.entries(r.weights_pct).map(([k, v]) => `${k}: ${v.toFixed(1)}%`).join("\n")}>{Object.keys(r.weights_pct).join(", ")}</span>, csv: (r) => Object.keys(r.weights_pct).join(" ") },
    { key: "w", label: "Combined weight", align: "right", render: (r) => <span className="num">{`${fmtNum(r.combined_weight_pct, 1)}%`}</span>, csv: (r) => r.combined_weight_pct },
    { key: "v", label: "Total value", align: "right", render: (r) => <span className="num">{fmtMoney(r.total_value_usd)}</span>, csv: (r) => r.total_value_usd },
  ];
  return (
    <Block fixed={!onRemove} onRemove={onRemove} sec title={data ? `Consensus across ${n} managers` : "Consensus"} loading={loading} error={error} fetchedAt={fetchedAt}
      actions={data?.rows.length ? <Button size="small" onClick={() => downloadCsv("consensus.csv", tableCsv(cols, data.rows))}>Export CSV</Button> : undefined}>
      {!data && !error && <span style={{ color: "var(--dim)" }}>Comparing every tracked manager's latest 13F (first run maps tickers; can take a minute)…</span>}
      {data && (
        <>
          <Caption1 style={{ color: "var(--dim)" }}>{data.managers.map((m) => m.label).join(" / ")}</Caption1>
          <DataTable columns={cols} rows={data.rows} rowKey={(r) => r.cusip} empty="No overlapping positions found." />
        </>
      )}
    </Block>
  );
}

export function PositionHistoryPanel({ manager, query, onRemove }: P & { manager: string; query: string }) {
  const { data, loading, error, fetchedAt } = useApi(`phist:${manager}:${query}`, () => api.positionHistory(manager, query, 8));
  const maxV = Math.max(...(data?.quarters ?? []).map((q) => q.value_usd), 1);
  return (
    <Block fixed={!onRemove} onRemove={onRemove} sec title={data ? `${data.issuer} · CUSIP ${data.cusips.join(", ")}` : "Position history"} loading={loading} error={error} fetchedAt={fetchedAt}>
      {data && (
        <table className="dt">
          <thead><tr><th>Period</th><th>Value</th><th style={{ textAlign: "right" }}>Shares</th><th style={{ textAlign: "right" }}>Weight</th></tr></thead>
          <tbody>
            {data.quarters.map((q, i) => {
              const d = i ? q.shares - data.quarters[i - 1].shares : 0;
              return (
                <tr key={`${q.period_of_report}:${i}`}>
                  <td>{q.period_of_report ?? "?"}</td>
                  <td>
                    <span className="num">{fmtMoney(q.value_usd)}</span>
                    <span style={{ display: "inline-block", verticalAlign: "middle", marginLeft: 8, height: 8, width: (q.value_usd / maxV) * 160, background: "var(--accent)", borderRadius: 3 }} />
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <span className="num">{fmtInt(q.shares)}</span>
                    {d !== 0 && <span className="num" style={{ marginLeft: 6, color: d > 0 ? "var(--up)" : "var(--down)" }}>{`(${signed(d, 0)})`}</span>}
                  </td>
                  <td style={{ textAlign: "right" }}><span className="num">{`${fmtNum(q.weight_pct, 1)}%`}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </Block>
  );
}

const BUY_COLS: Column<InsiderBuy>[] = [
  { key: "d", label: "Date", render: (r) => r.date ?? "?", csv: (r) => r.date },
  { key: "s", label: "Symbol", render: (r) => <Ticker symbol={r.symbol} />, csv: (r) => r.symbol },
  { key: "i", label: "Insider", render: (r) => <span title={r.relationship ?? undefined}>{r.insider}</span>, csv: (r) => r.insider },
  { key: "sh", label: "Shares", align: "right", render: (r) => num(fmtInt(r.shares)), csv: (r) => r.shares },
  { key: "p", label: "Price", align: "right", render: (r) => num(fmtNum(r.price_per_share)), csv: (r) => r.price_per_share },
  { key: "v", label: "Value", align: "right", render: (r) => num(fmtMoney(r.value_usd)), csv: (r) => r.value_usd },
];

export function InsiderBuysPanel({ list, title = "Open-market insider buys", onRemove }: P & { list: string[]; title?: string }) {
  const symbols = list;
  const { data, loading, error, fetchedAt } = useApi(symbols.length ? `ibuys:${symbols.join(",")}` : null, () => api.insiderBuys(symbols, 8));
  return (
    <Block fixed={!onRemove} onRemove={onRemove} sec title={title} loading={loading} error={error} fetchedAt={fetchedAt}>
      {!symbols.length && <span style={{ color: "var(--dim)" }}>Add stock symbols to this watchlist (Portfolio → Watchlists) to screen them.</span>}
      {symbols.length > 0 && !data && !error && <span style={{ color: "var(--dim)" }}>{`Scanning Form 4s for ${symbols.length} symbols (first run is the slow one)…`}</span>}
      {data && (
        <>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, color: "var(--up)" }}>
            {data.summary.map((s) => <span key={s.symbol} className="num">{`${s.symbol} ${s.buy_count}× ${fmtMoney(s.total_value_usd)}`}</span>)}
          </div>
          <DataTable columns={BUY_COLS} rows={data.buys.slice(0, 50)} rowKey={(r) => `${r.accession_number}:${r.symbol}:${r.insider}:${r.date}:${r.shares}`}
            empty={`No open-market insider buys across ${symbols.join(", ")} in their last 8 Form 4s each. (Insider buying is rare — that's why it matters.)`} />
        </>
      )}
    </Block>
  );
}

const FUND_COLS: Column<FundHolding>[] = [
  { key: "n", label: "Holding", render: (r) => <span title={r.title ?? undefined}>{r.name}</span>, csv: (r) => r.name },
  { key: "v", label: "Value", align: "right", render: (r) => <span className="num">{fmtMoney(r.value_usd)}</span>, csv: (r) => r.value_usd },
  { key: "p", label: "% of fund", align: "right", render: (r) => <span className="num">{`${fmtNum(r.pct_val, 2)}%`}</span>, csv: (r) => r.pct_val },
  { key: "a", label: "Asset", render: (r) => r.asset_cat ?? "—", csv: (r) => r.asset_cat },
  { key: "c", label: "Country", render: (r) => r.country ?? "—", csv: (r) => r.country },
];

export function FundPanel({ symbol, top = 50, onRemove }: P & { symbol: string; top?: number }) {
  const { data, loading, error, fetchedAt } = useApi(`fund:${symbol}:${top}`, () => api.fund(symbol, top));
  return (
    <Block fixed={!onRemove} onRemove={onRemove} sec title={data?.fund || `Fund holdings · ${symbol}`} loading={loading} error={error} fetchedAt={fetchedAt}
      actions={data?.holdings.length ? <Button size="small" onClick={() => downloadCsv(`${symbol}-holdings.csv`, tableCsv(FUND_COLS, data.holdings))}>Export CSV</Button> : undefined}>
      {data && (
        <>
          <Caption1 style={{ color: "var(--dim)" }}>{`as of ${data.report_period_date ?? "?"} · net assets ${fmtMoney(data.net_assets)} · ${data.position_count} positions`}</Caption1>
          <DataTable columns={FUND_COLS} rows={data.holdings} rowKey={(r, i) => `${r.cusip ?? r.name}:${i}`} empty="No holdings reported." />
        </>
      )}
    </Block>
  );
}
