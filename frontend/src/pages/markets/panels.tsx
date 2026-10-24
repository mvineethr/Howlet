import { useApi } from "../../lib/useApi";
import { api } from "../../lib/api";
import { fmtNum } from "../../lib/fmt";
import Block from "../../blocks/Block";
import DataTable from "../../components/DataTable";
import NewsList from "../../components/NewsList";

const FIVE_MIN = 300_000, HOUR = 3_600_000;

type P = { onRemove?: () => void };

export function YieldCurvePanel({ onRemove }: P) {
  const macro = useApi("macro", api.macro, HOUR);
  const m = macro.data;
  const curve = m?.treasury_yield_curve?.curve ?? [];
  return (
    <Block fixed={!onRemove} onRemove={onRemove} title={`Treasury yield curve${m?.treasury_yield_curve?.date ? ` · ${m.treasury_yield_curve.date}` : ""}`}
      loading={macro.loading} error={macro.error} fetchedAt={macro.fetchedAt} refreshMs={HOUR}>
      {!m && !macro.error && <span style={{ color: "var(--dim)" }}>Loading macro (Treasury, BLS, FRED)…</span>}
      {m && (curve.length ? (
        <DataTable columns={[
          { key: "m", label: "Maturity", render: (r) => r.maturity },
          { key: "y", label: "Yield", align: "right", render: (r) => <span className="num">{fmtNum(r.yield_pct)}%</span> },
        ]} rows={curve} rowKey={(r) => r.maturity} empty="Yield curve unavailable right now." />
      ) : <span style={{ color: "var(--dim)" }}>Yield curve unavailable right now.</span>)}
    </Block>
  );
}

export function FedPanel({ limit = 20, onRemove }: P & { limit?: number }) {
  const fed = useApi(`fed:${limit}`, () => api.fedEvents(limit), FIVE_MIN);
  return (
    <Block fixed={!onRemove} onRemove={onRemove} title="Fed calendar" loading={fed.loading} error={fed.error} fetchedAt={fed.fetchedAt} refreshMs={FIVE_MIN}>
      {fed.data && <NewsList items={fed.data} empty="No Fed items right now." />}
    </Block>
  );
}
