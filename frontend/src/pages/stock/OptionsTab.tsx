import { Dropdown, Option } from "@fluentui/react-components";
import { useState } from "react";
import { useApi } from "../../lib/useApi";
import { api, type OptionContract } from "../../lib/api";
import { fmtInt, fmtNum } from "../../lib/fmt";
import Block from "../../blocks/Block";
import DataTable, { type Column } from "../../components/DataTable";

const n = (s: string) => <span className="num">{s}</span>;
const COLS: Column<OptionContract>[] = [
  { key: "k", label: "Strike", align: "right", render: (r) => <span className="num" style={r.in_the_money ? { fontWeight: 600, color: "var(--up)" } : undefined}>{fmtNum(r.strike)}</span> },
  { key: "l", label: "Last", align: "right", render: (r) => n(fmtNum(r.last_price)) },
  { key: "b", label: "Bid", align: "right", render: (r) => n(fmtNum(r.bid)) },
  { key: "a", label: "Ask", align: "right", render: (r) => n(fmtNum(r.ask)) },
  { key: "v", label: "Volume", align: "right", render: (r) => n(fmtInt(r.volume)) },
  { key: "o", label: "Open int.", align: "right", render: (r) => n(fmtInt(r.open_interest)) },
  { key: "iv", label: "IV", align: "right", render: (r) => n(r.implied_volatility == null ? "—" : `${fmtNum(r.implied_volatility * 100, 1)}%`) },
];

export default function OptionsTab({ symbol }: { symbol: string }) {
  const [expiration, setExpiration] = useState<string | undefined>();
  const { data, error, loading, fetchedAt } = useApi(`options:${symbol}:${expiration ?? ""}`, () => api.options(symbol, expiration));
  const sel = data?.selected_expiration ?? expiration ?? "";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        {data && <span>Underlying <span className="num">{fmtNum(data.underlying_price)}</span></span>}
        {data && data.expiration_dates.length > 0 && (
          <Dropdown size="small" value={sel} selectedOptions={[sel]} onOptionSelect={(_, d) => setExpiration(d.optionValue)} aria-label="Expiration">
            {data.expiration_dates.map((d) => <Option key={d} value={d}>{d}</Option>)}
          </Dropdown>
        )}
        <span style={{ color: "var(--dim)" }}>Experimental — unofficial Yahoo data, may go dark.</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: 12, alignItems: "start" }}>
        <Block fixed title="Calls" loading={loading} error={error} fetchedAt={fetchedAt}>
          {data && <DataTable columns={COLS} rows={data.calls} rowKey={(r) => r.contract_symbol} empty="No contracts." />}
        </Block>
        <Block fixed title="Puts" loading={loading} error={error} fetchedAt={fetchedAt}>
          {data && <DataTable columns={COLS} rows={data.puts} rowKey={(r) => r.contract_symbol} empty="No contracts." />}
        </Block>
      </div>
    </div>
  );
}
