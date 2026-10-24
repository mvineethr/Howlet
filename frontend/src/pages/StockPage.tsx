import { Body1, Card, Tab, TabList, Title2 } from "@fluentui/react-components";
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import { useRoute, type StockTab } from "../lib/route";
import { REFRESH_MS, useSettings } from "../lib/settings";
import Num from "../components/Num";
import OwlChips from "../components/OwlChips";
import PlaceholderPage from "./PlaceholderPage";

const TABS: [StockTab, string][] = [["overview", "Overview"], ["chart", "Chart"], ["financials", "Financials"], ["holders", "Holders"], ["news", "News"], ["options", "Options"]];

export default function StockPage({ symbol, tab }: { symbol: string; tab: StockTab }) {
  const { showOptions, refresh } = useSettings((s) => s.settings);
  const go = useRoute((r) => r.go);
  const { data: q, error } = useApi(`sec:${symbol}`, () => api.security(symbol), REFRESH_MS[refresh]);
  const tabs = TABS.filter(([t]) => t !== "options" || showOptions);

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <Title2>{symbol}</Title2>
        {q && <Body1 style={{ color: "var(--dim)" }}>{q.name}</Body1>}
        {q && <span style={{ fontSize: "1.6em" }}><Num value={q.price} /></span>}
        {q && <Num value={q.change_pct} pct />}
        {error && !q && <Body1 style={{ color: "var(--dim)" }}>Quote unavailable</Body1>}
      </div>
      <OwlChips symbol={symbol} />
      <TabList selectedValue={tab} onTabSelect={(_, d) => go({ kind: "stock", symbol, tab: d.value as StockTab })}>
        {tabs.map(([t, label]) => <Tab key={t} value={t}>{label}</Tab>)}
      </TabList>
      {tab === "overview" && q ? (
        <Card style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
          {([
            ["Previous close", q.previous_close], ["Day low", q.day_low], ["Day high", q.day_high],
            ["52-week low", q.week52_low], ["52-week high", q.week52_high], ["Volume", q.volume],
          ] as [string, number | null][]).map(([k, v]) => (
            <div key={k}><div style={{ color: "var(--dim)" }}>{k}</div><Num value={v} digits={k === "Volume" ? 0 : 2} flash={false} /></div>
          ))}
        </Card>
      ) : tab !== "overview" ? (
        <PlaceholderPage title={TABS.find(([t]) => t === tab)?.[1] ?? tab} />
      ) : null}
    </div>
  );
}
