import { Tag, TagGroup, Tooltip } from "@fluentui/react-components";
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";

export default function OwlChips({ symbol }: { symbol: string }) {
  // Holders come from SEC 13Fs, which are immutable per quarter: no refresh timer.
  const { data, error } = useApi(`holders:${symbol}`, () => api.holders(symbol));
  if (error || !data || !data.holders.length) return null;
  const holders = [...data.holders].sort((a, b) => b.weight_pct - a.weight_pct);
  return (
    <TagGroup aria-label="Tracked superinvestors holding this stock" style={{ flexWrap: "wrap", gap: 4 }}>
      {holders.map((h) => (
        <Tooltip key={h.manager + h.issuer} relationship="description"
          content={`${h.shares.toLocaleString()} shares · $${(h.value_usd / 1e6).toFixed(0)}M · period ${h.period_of_report ?? "?"}`}>
          <Tag size="small" appearance="brand">🦉 {h.manager} · {h.weight_pct.toFixed(1)}%</Tag>
        </Tooltip>
      ))}
    </TagGroup>
  );
}
