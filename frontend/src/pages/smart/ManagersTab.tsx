import { Badge, Button, Caption1 } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type DiffChange } from "../../lib/api";
import { fmtMoney, fmtNum, signed, tone } from "../../lib/fmt";
import { downloadCsv } from "../../lib/csv";
import { useRoute } from "../../lib/route";
import Block from "../../blocks/Block";
import DataTable, { tableCsv, type Column } from "../../components/DataTable";
import NewsList from "../../components/NewsList";
import ManagerPicker from "../../components/ManagerPicker";
import { HoldingsPanel } from "./panels";

const FIVE_MIN = 300_000;
const STATUS = { NEW: "success", INCREASED: "success", DECREASED: "warning", SOLD: "danger" } as const;
const num = (s: string, style?: { color?: string }) => <span className="num" style={style}>{s}</span>;
const usdChange = (v: number) => `${v >= 0 ? "+" : "-"}${fmtMoney(Math.abs(v))}`;

const CHANGE_COLS: Column<DiffChange>[] = [
  { key: "s", label: "Status", render: (r) => <Badge size="small" appearance="tint" color={STATUS[r.status as keyof typeof STATUS] ?? "informative"}>{r.status}</Badge>, csv: (r) => r.status },
  { key: "i", label: "Issuer", render: (r) => r.issuer, csv: (r) => r.issuer },
  { key: "v", label: "Value change", align: "right", render: (r) => num(usdChange(r.value_change_usd), { color: tone(r.value_change_usd) }), csv: (r) => r.value_change_usd },
  { key: "sh", label: "Shares change", align: "right", render: (r) => num(signed(r.shares_change, 0), { color: "var(--dim)" }), csv: (r) => r.shares_change },
];

export default function ManagersTab({ manager }: { manager: string }) {
  const go = useRoute((r) => r.go);
  const port = useApi(`portfolio:${manager}`, () => api.portfolio(manager, 25));
  const diff = useApi(`diff:${manager}`, () => api.diff(manager));
  const tickers = (port.data?.positions ?? []).map((p) => p.ticker).filter((t): t is string => !!t).slice(0, 8);
  const news = useApi(port.data ? `mgrnews:${manager}:${tickers.join(",")}` : null, () => api.newsFor(tickers, 25), FIVE_MIN);
  const top = (port.data?.positions ?? []).slice(0, 10);
  const maxW = Math.max(...top.map((p) => p.weight_pct), 0.0001);
  const d = port.data;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ width: 260 }}>
        <ManagerPicker key={manager} value={manager} onPick={(m) => go({ kind: "page", page: "smart", params: ["managers", m] })} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12, alignItems: "start" }}>
        <div style={{ gridColumn: "1 / -1" }}>
          <HoldingsPanel manager={manager} />
        </div>
        <Block fixed sec title="Allocation · top 10" loading={port.loading} error={port.error} fetchedAt={port.fetchedAt}>
          {d && (top.length ? top.map((p) => (
            <div key={p.cusip} style={{ display: "grid", gridTemplateColumns: "110px 1fr 56px", gap: 8, alignItems: "center", padding: "2px 0" }}>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.ticker ?? p.issuer}</span>
              <span style={{ background: "var(--elev-1)", height: 10, borderRadius: 3 }}>
                <span style={{ display: "block", height: "100%", width: `${(p.weight_pct / maxW) * 100}%`, background: "var(--accent)", borderRadius: 3 }} />
              </span>
              <span className="num" style={{ textAlign: "right" }}>{`${fmtNum(p.weight_pct, 1)}%`}</span>
            </div>
          )) : <span style={{ color: "var(--dim)" }}>No positions.</span>)}
        </Block>
        <Block fixed sec title="Q/Q changes" loading={diff.loading} error={diff.error} fetchedAt={diff.fetchedAt}
          actions={diff.data?.changes.length ? <Button size="small" onClick={() => downloadCsv(`${manager}-changes.csv`, tableCsv(CHANGE_COLS, diff.data!.changes))}>Export CSV</Button> : undefined}>
          {diff.data && (
            <>
              <Caption1 style={{ color: "var(--dim)" }}>{`${diff.data.prior_period ?? "?"} → ${diff.data.current_period ?? "?"}`}</Caption1>
              <DataTable columns={CHANGE_COLS} rows={diff.data.changes.slice(0, 40)} rowKey={(r) => r.cusip} empty="No changes between the last two filings." />
            </>
          )}
        </Block>
        <Block fixed title={tickers.length ? `News · ${tickers.join(", ")}` : "News"} loading={news.loading} error={news.error} fetchedAt={news.fetchedAt} refreshMs={FIVE_MIN}>
          {news.data && <NewsList items={news.data} empty="No headlines right now." />}
        </Block>
      </div>
    </div>
  );
}
