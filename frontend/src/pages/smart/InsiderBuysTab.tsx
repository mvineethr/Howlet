import { useState } from "react";
import { Dropdown, Option } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type InsiderBuy } from "../../lib/api";
import { fmtInt, fmtMoney, fmtNum } from "../../lib/fmt";
import { getWatchlists } from "../../lib/legacy";
import Block from "../../blocks/Block";
import DataTable, { type Column } from "../../components/DataTable";
import Ticker from "../../components/Ticker";

// Indices, FX, futures and crypto have no Form 4s.
export const stockSymbols = (list: string[]): string[] =>
  list.filter((s) => !s.startsWith("^") && !s.includes("=") && !s.includes("-USD"));

const num = (s: string) => <span className="num">{s}</span>;
const COLS: Column<InsiderBuy>[] = [
  { key: "d", label: "Date", render: (r) => r.date ?? "?", csv: (r) => r.date },
  { key: "s", label: "Symbol", render: (r) => <Ticker symbol={r.symbol} />, csv: (r) => r.symbol },
  { key: "i", label: "Insider", render: (r) => <span title={r.relationship ?? undefined}>{r.insider}</span>, csv: (r) => r.insider },
  { key: "sh", label: "Shares", align: "right", render: (r) => num(fmtInt(r.shares)), csv: (r) => r.shares },
  { key: "p", label: "Price", align: "right", render: (r) => num(fmtNum(r.price_per_share)), csv: (r) => r.price_per_share },
  { key: "v", label: "Value", align: "right", render: (r) => num(fmtMoney(r.value_usd)), csv: (r) => r.value_usd },
];

export default function InsiderBuysTab() {
  const lists = getWatchlists();
  const names = Object.keys(lists);
  const [name, setName] = useState(names.includes("default") ? "default" : names[0]);
  const symbols = stockSymbols(lists[name] ?? []).slice(0, 15);
  const { data, loading, error, fetchedAt } = useApi(symbols.length ? `ibuys:${symbols.join(",")}` : null, () => api.insiderBuys(symbols, 8));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ width: 260 }}>
        <Dropdown size="small" aria-label="Watchlist" value={name} selectedOptions={[name]} onOptionSelect={(_, d) => d.optionValue && setName(d.optionValue)}>
          {names.map((n) => <Option key={n} value={n}>{n}</Option>)}
        </Dropdown>
      </div>
      {!symbols.length ? (
        <span style={{ color: "var(--dim)" }}>Add stock symbols to this watchlist (Portfolio → Watchlists) to screen them.</span>
      ) : (
        <Block fixed sec title="Open-market insider buys" loading={loading} error={error} fetchedAt={fetchedAt}>
          {!data && !error && <span style={{ color: "var(--dim)" }}>{`Scanning Form 4s for ${symbols.length} symbols (first run is the slow one)…`}</span>}
          {data && (
            <>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, color: "var(--up)" }}>
                {data.summary.map((s) => <span key={s.symbol} className="num">{`${s.symbol} ${s.buy_count}× ${fmtMoney(s.total_value_usd)}`}</span>)}
              </div>
              <DataTable columns={COLS} rows={data.buys.slice(0, 50)} rowKey={(r) => `${r.accession_number}:${r.symbol}:${r.insider}:${r.date}:${r.shares}`}
                empty={`No open-market insider buys across ${symbols.join(", ")} in their last 8 Form 4s each. (Insider buying is rare — that's why it matters.)`} />
            </>
          )}
        </Block>
      )}
    </div>
  );
}
