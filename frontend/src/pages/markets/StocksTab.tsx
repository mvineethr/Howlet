import { useApi } from "../../lib/useApi";
import { api } from "../../lib/api";
import { REFRESH_MS, useSettings } from "../../lib/settings";
import { fmtNum, signed, tone } from "../../lib/fmt";
import Block from "../../blocks/Block";
import Ticker from "../../components/Ticker";
import Sparkline from "../../components/Sparkline";

export default function StocksTab() {
  // one /api/markets call is ~30 throttled Yahoo requests: never poll faster than classic (5 min)
  const refreshMs = Math.max(REFRESH_MS[useSettings((s) => s.settings.refresh)], 300_000);
  const { data, error, loading, fetchedAt } = useApi("markets", api.markets, refreshMs);
  if (!data) {
    return (
      <Block fixed title="World markets" loading={loading} error={error} fetchedAt={fetchedAt} refreshMs={refreshMs}>
        {!error && <span style={{ color: "var(--dim)" }}>Loading world markets (30+ instruments)…</span>}
      </Block>
    );
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 12 }}>
      {data.map((sec) => (
        <Block fixed key={sec.section} title={sec.section} error={error} fetchedAt={fetchedAt} refreshMs={refreshMs}>
          <table className="dt">
            <tbody>
              {sec.rows.map((r) => (
                <tr key={r.symbol}>
                  <td><Ticker symbol={r.symbol} /></td>
                  <td style={{ color: "var(--dim)" }}>{r.label}</td>
                  <td className="num" style={{ textAlign: "right" }}>{fmtNum(r.price)}</td>
                  <td className="num" style={{ textAlign: "right", color: tone(r.change_pct) }}>{r.change_pct == null ? "—" : `${signed(r.change_pct)}%`}</td>
                  <td><Sparkline values={r.sparkline} w={60} h={14} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Block>
      ))}
    </div>
  );
}
