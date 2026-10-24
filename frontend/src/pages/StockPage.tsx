import { Body1, Tab, TabList, Title2 } from "@fluentui/react-components";
import { useApi } from "../lib/useApi";
import { api, type SecurityDetail } from "../lib/api";
import { useRoute, type StockTab } from "../lib/route";
import { REFRESH_MS, useSettings } from "../lib/settings";
import Num from "../components/Num";
import OwlChips from "../components/OwlChips";
import OverviewTab from "./stock/OverviewTab";
import ChartTab from "./stock/ChartTab";
import FinancialsTab from "./stock/FinancialsTab";
import HoldersTab from "./stock/HoldersTab";
import NewsTab from "./stock/NewsTab";
import OptionsTab from "./stock/OptionsTab";

const TABS: [StockTab, string][] = [["overview", "Overview"], ["chart", "Chart"], ["financials", "Financials"], ["holders", "Holders"], ["news", "News"], ["options", "Options"]];

const BODY: Record<StockTab, (s: string, q: SecurityDetail | undefined) => JSX.Element> = {
  overview: (s, q) => <OverviewTab symbol={s} q={q} />,
  chart: (s) => <ChartTab symbol={s} />,
  financials: (s) => <FinancialsTab symbol={s} />,
  holders: (s) => <HoldersTab symbol={s} />,
  news: (s) => <NewsTab symbol={s} />,
  options: (s) => <OptionsTab symbol={s} />,
};

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
      <div key={symbol}>{(BODY[tab === "options" && !showOptions ? "overview" : tab] ?? BODY.overview)(symbol, q)}</div>
    </div>
  );
}
