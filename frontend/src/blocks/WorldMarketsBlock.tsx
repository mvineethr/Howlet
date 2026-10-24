import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import { REFRESH_MS, useSettings } from "../lib/settings";
import { fmtNum, signed, tone } from "../lib/fmt";
import Ticker from "../components/Ticker";
import Block from "./Block";

export default function WorldMarketsBlock({ onRemove }: { onRemove?: () => void }) {
  // one /api/markets call is ~30 throttled Yahoo requests: never poll faster than 5 min
  const refreshMs = Math.max(REFRESH_MS[useSettings((s) => s.settings.refresh)], 300_000);
  const { data, error, loading, fetchedAt } = useApi("markets", api.markets, refreshMs);
  return (
    <Block title="World markets" {...{ loading, error, fetchedAt, refreshMs, onRemove }}>
      {data && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
          {data.map((sec) => (
            <div key={sec.section} style={{ flex: "1 1 240px", minWidth: 240 }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>{sec.section}</div>
              <table className="dt">
                <tbody>
                  {sec.rows.map((r) => (
                    <tr key={r.symbol}>
                      <td><Ticker symbol={r.symbol} /></td>
                      <td style={{ color: "var(--dim)" }}>{r.label}</td>
                      <td className="num" style={{ textAlign: "right" }}>{fmtNum(r.price)}</td>
                      <td className="num" style={{ textAlign: "right", color: tone(r.change_pct) }}>{r.change_pct == null ? "—" : `${signed(r.change_pct)}%`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </Block>
  );
}
