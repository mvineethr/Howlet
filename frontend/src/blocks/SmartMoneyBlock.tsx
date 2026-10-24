import { Badge } from "@fluentui/react-components";
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import Block from "./Block";

const fmtUsd = (v: number) => `${v < 0 ? "−" : "+"}$${(Math.abs(v) / 1e6).toLocaleString(undefined, { maximumFractionDigits: 0 })}M`;
// Status strings from src/howlet/diff.py (UNCHANGED is filtered out by the API).
const COLOR = { NEW: "success", INCREASED: "success", DECREASED: "warning", SOLD: "danger" } as const;

export default function SmartMoneyBlock({ manager = "buffett", onRemove }: { manager?: string; onRemove?: () => void }) {
  // SEC data: immutable per quarter, so refresh hourly at most.
  const { data, error, loading, fetchedAt } = useApi(`diff:${manager}`, () => api.diff(manager), 3_600_000);
  return (
    <Block title={`Smart money · ${manager}`} sec {...{ loading, error, fetchedAt, onRemove }}>
      {data && (
        <>
          <div style={{ color: "var(--dim)", marginBottom: 4 }}>{data.prior_period} → {data.current_period}</div>
          {data.changes.slice(0, 12).map((c) => (
            <div key={c.cusip} style={{ display: "flex", gap: 8, alignItems: "center", padding: "3px 0", borderBottom: "1px solid var(--hair)" }}>
              <Badge size="small" appearance="tint" color={COLOR[c.status as keyof typeof COLOR] ?? "informative"}>{c.status}</Badge>
              <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.issuer}</span>
              <span style={{ fontFamily: "var(--font-mono)" }}>{fmtUsd(c.value_change_usd)}</span>
            </div>
          ))}
        </>
      )}
    </Block>
  );
}
