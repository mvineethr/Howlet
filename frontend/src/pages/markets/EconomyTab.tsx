import { useApi } from "../../lib/useApi";
import { api, type NewsItem, type RegDoc } from "../../lib/api";
import { fmtNum } from "../../lib/fmt";
import Block from "../../blocks/Block";
import DataTable from "../../components/DataTable";
import NewsList from "../../components/NewsList";

const HOUR = 3_600_000, FIVE_MIN = 300_000;
const BLS_LABELS: [string, string][] = [["cpi", "CPI (all items)"], ["unemployment_rate", "Unemployment rate"], ["nonfarm_payrolls", "Nonfarm payrolls"]];

export const regToNews = (d: RegDoc): NewsItem => ({
  title: d.title, link: d.html_url,
  source: [d.type ?? "Document", d.publication_date].filter(Boolean).join(" · "),
  symbol: null, published: null,
});

export default function EconomyTab() {
  const macro = useApi("macro", api.macro, HOUR);
  const fed = useApi("fed:20", () => api.fedEvents(20), FIVE_MIN);
  const reg = useApi("reg:15", () => api.regulatory(15), HOUR);
  const m = macro.data;
  const curve = m?.treasury_yield_curve?.curve ?? [];
  const bls = BLS_LABELS.map(([k, label]) => ({ k, label, p: m?.bls_series?.[k]?.[0] })).filter((r) => r.p);
  const fred = Object.entries(m?.fred_series ?? {});
  const box = { height: "calc((100vh - 170px) / 2)" };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))", gap: 12 }}>
      <div style={box}>
        <Block fixed title={`Treasury yield curve${m?.treasury_yield_curve?.date ? ` · ${m.treasury_yield_curve.date}` : ""}`}
          loading={macro.loading} error={macro.error} fetchedAt={macro.fetchedAt} refreshMs={HOUR}>
          {m && (curve.length ? (
            <DataTable columns={[
              { key: "m", label: "Maturity", render: (r) => r.maturity },
              { key: "y", label: "Yield", align: "right", render: (r) => <span className="num">{fmtNum(r.yield_pct)}%</span> },
            ]} rows={curve} rowKey={(r) => r.maturity} empty="Yield curve unavailable right now." />
          ) : <span style={{ color: "var(--dim)" }}>Yield curve unavailable right now.</span>)}
        </Block>
      </div>
      <div style={box}>
        <Block fixed title="Jobs & inflation" loading={macro.loading} error={macro.error} fetchedAt={macro.fetchedAt} refreshMs={HOUR}>
          {m && (
            <>
              {bls.length ? (
                <DataTable columns={[
                  { key: "l", label: "Series", render: (r) => r.label },
                  { key: "v", label: "Latest", align: "right", render: (r) => <span className="num">{r.p!.value}</span> },
                  { key: "p", label: "Period", render: (r) => `${r.p!.period} ${r.p!.year}` },
                ]} rows={bls} rowKey={(r) => r.k} empty="" />
              ) : <div style={{ color: "var(--dim)" }}>BLS series unavailable right now (keyless tier is rate-limited to 25 requests/day/IP).</div>}
              {fred.length > 0 && (
                <>
                  <div style={{ marginTop: 10, fontWeight: 600 }}>FRED (St. Louis Fed)</div>
                  <DataTable columns={[
                    { key: "d", label: "Series", render: ([, v]) => v.description },
                    { key: "l", label: "Latest", align: "right", render: ([, v]) => <span className="num">{v.latest ?? "—"}</span> },
                    { key: "t", label: "Date", render: ([, v]) => v.date ?? "—" },
                  ]} rows={fred} rowKey={([k]) => k} empty="" />
                </>
              )}
              {!fred.length && !m.fred_available && (
                <div style={{ color: "var(--dim)", marginTop: 10 }}>
                  Set FRED_API_KEY for deeper macro coverage (GDP, Fed funds rate, mortgage rates…) — free signup at fred.stlouisfed.org.
                </div>
              )}
            </>
          )}
        </Block>
      </div>
      <div style={box}>
        <Block fixed title="Fed calendar" loading={fed.loading} error={fed.error} fetchedAt={fed.fetchedAt} refreshMs={FIVE_MIN}>
          {fed.data && <NewsList items={fed.data} empty="No Fed items right now." />}
        </Block>
      </div>
      <div style={box}>
        <Block fixed title="SEC rulemaking" loading={reg.loading} error={reg.error} fetchedAt={reg.fetchedAt} refreshMs={HOUR}>
          {reg.data && <NewsList items={reg.data.map(regToNews)} empty="Federal Register unavailable right now." />}
        </Block>
      </div>
    </div>
  );
}
