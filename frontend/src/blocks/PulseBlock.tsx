import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import { REFRESH_MS, useSettings } from "../lib/settings";
import Num from "../components/Num";
import Block from "./Block";

export default function PulseBlock({ onRemove }: { onRemove?: () => void }) {
  const refreshMs = REFRESH_MS[useSettings((s) => s.settings.refresh)];
  const { data, error, loading, fetchedAt } = useApi("tape", api.tape, refreshMs);
  return (
    <Block title="Market pulse" {...{ loading, error, fetchedAt, refreshMs, onRemove }}>
      {data && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 8 }}>
          {data.map((r) => (
            <div key={r.symbol} style={{ background: "var(--elev-1)", borderRadius: 6, padding: "6px 8px" }}>
              <div style={{ color: "var(--dim)", fontSize: "0.85em" }}>{r.label}</div>
              <Num value={r.price} /> <Num value={r.change_pct} pct />
            </div>
          ))}
        </div>
      )}
    </Block>
  );
}
