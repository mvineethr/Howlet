import { Caption1 } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type CryptoRow } from "../../lib/api";
import { REFRESH_MS, useSettings } from "../../lib/settings";
import { fmtMoney, fmtNum, priceDigits, signed, tone } from "../../lib/fmt";
import Block from "../../blocks/Block";
import DataTable, { type Column } from "../../components/DataTable";

const px = (p: number | null) => (p == null ? "—" : `$${fmtNum(p, priceDigits(p))}`);

const COLS: Column<CryptoRow>[] = [
  { key: "rank", label: "#", render: (r) => <span style={{ color: "var(--dim)" }}>{r.rank}</span> },
  { key: "coin", label: "Coin", render: (r) => <><b>{r.symbol}</b> <span style={{ color: "var(--dim)" }}>{r.name}</span></> },
  { key: "price", label: "Price", align: "right", render: (r) => <span className="num">{px(r.price)}</span> },
  { key: "chg", label: "24h %", align: "right", render: (r) => <span className="num" style={{ color: tone(r.change_pct_24h) }}>{r.change_pct_24h == null ? "—" : `${signed(r.change_pct_24h)}%`}</span> },
  { key: "cap", label: "Mkt cap", align: "right", render: (r) => <span className="num">{fmtMoney(r.market_cap)}</span> },
  { key: "vol", label: "24h volume", align: "right", render: (r) => <span className="num">{fmtMoney(r.volume_24h)}</span> },
  { key: "range", label: "24h low / high", align: "right", render: (r) => <span className="num">{r.low_24h == null ? "—" : `${px(r.low_24h)} / ${px(r.high_24h)}`}</span> },
];

export default function CryptoTab() {
  const refreshMs = REFRESH_MS[useSettings((s) => s.settings.refresh)];
  const { data, error, loading, fetchedAt } = useApi("crypto:50", () => api.crypto(50), refreshMs);
  return (
    <Block fixed title={`Crypto · top ${data?.rows.length ?? 50} by market cap · 24h`} loading={loading} error={error}
      fetchedAt={fetchedAt} refreshMs={refreshMs} actions={data?.source ? <Caption1 style={{ color: "var(--dim)" }}>source: {data.source}</Caption1> : undefined}>
      {data && <DataTable columns={COLS} rows={data.rows} rowKey={(r) => r.symbol}
        empty="Crypto data unavailable right now (CoinGecko and Coinpaprika both unreachable)." />}
    </Block>
  );
}
