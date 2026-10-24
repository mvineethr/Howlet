import { Caption1, Text } from "@fluentui/react-components";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { signed, tone } from "../lib/fmt";
import { usd } from "../lib/paper";
import Block from "./Block";
import Ticker from "../components/Ticker";

export default function PaperBlock({ onRemove }: { onRemove?: () => void }) {
  const { data, loading, error, fetchedAt } = useApi("paper-block", () => api.paperAccount(), 60_000);
  const a = data?.account ? data : null;
  return (
    <Block title="Paper account" {...{ loading, error, fetchedAt, refreshMs: 60_000, onRemove }} fixed={!onRemove}>
      {data && !a && <Caption1 style={{ color: "var(--dim)" }}>No paper account yet — open Portfolio → Paper to start one.</Caption1>}
      {a && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <Text size={500} weight="semibold" className="num">{usd(a.equity)}</Text>
          <span className="num" style={{ color: tone(a.day_change) }}>{`${usd(a.day_change)} today`}</span>
          <span className="num" style={{ color: tone(a.total_return_pct) }}>{`${signed(a.total_return_pct, 1)}% total`}</span>
          {a.positions.slice(0, 5).map((p) => (
            <div key={p.symbol} style={{ display: "flex", justifyContent: "space-between" }}>
              <Ticker symbol={p.symbol} />
              <span className="num" style={{ color: tone(p.unrealized) }}>{usd(p.value)}</span>
            </div>
          ))}
        </div>
      )}
    </Block>
  );
}
