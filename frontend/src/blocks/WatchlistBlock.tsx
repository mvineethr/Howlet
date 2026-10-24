import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import { getWatchlists } from "../lib/legacy";
import { REFRESH_MS, useSettings } from "../lib/settings";
import { useRoute } from "../lib/route";
import Num from "../components/Num";
import Block from "./Block";

export default function WatchlistBlock({ list = "default", onRemove }: { list?: string; onRemove?: () => void }) {
  const refreshMs = REFRESH_MS[useSettings((s) => s.settings.refresh)];
  const symbols = getWatchlists()[list] ?? [];
  const go = useRoute((r) => r.go);
  const { data, error, loading, fetchedAt } = useApi(symbols.length ? `wl:${list}:${symbols.join(",")}` : null, () => api.quotes(symbols), refreshMs);
  return (
    <Block title={`Watchlist · ${list}`} {...{ loading, error, fetchedAt, refreshMs, onRemove }}>
      {!symbols.length && <span style={{ color: "var(--dim)" }}>Empty list — add symbols in the classic view's MY screen for now.</span>}
      {data && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <tbody>
            {data.map((q) => (
              <tr key={q.symbol} style={{ cursor: "pointer", borderBottom: "1px solid var(--hair)" }}
                onClick={() => go({ kind: "stock", symbol: q.symbol, tab: "overview" })}>
                <td style={{ padding: "4px 0" }}>{q.symbol}</td>
                <td style={{ textAlign: "right" }}><Num value={q.price} /></td>
                <td style={{ textAlign: "right", width: 72 }}><Num value={q.change_pct} pct /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Block>
  );
}
