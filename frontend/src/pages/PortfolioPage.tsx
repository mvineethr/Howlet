import { Caption1, Dropdown, Option, Tab, TabList } from "@fluentui/react-components";
import { useRoute } from "../lib/route";
import { readJson, writeJson } from "../lib/storage";
import WatchlistsTab from "./portfolio/WatchlistsTab";
import HoldingsTab from "./portfolio/HoldingsTab";

export type PortfolioTab = "watchlists" | "holdings";
const TABS: [PortfolioTab, string][] = [["watchlists", "Watchlists"], ["holdings", "Holdings & risk"]];
const KEY = "howlet_portfolio_tab_v1";
const isTab = (v: unknown): v is PortfolioTab => TABS.some(([t]) => t === v);

export default function PortfolioPage({ params }: { params: string[] }) {
  const go = useRoute((r) => r.go);
  const saved = readJson<string | null>(KEY, null, (v): v is string => typeof v === "string");
  const tab: PortfolioTab = isTab(params[0]) ? params[0] : isTab(saved) ? saved : "watchlists";
  const pick = (t: PortfolioTab) => { writeJson(KEY, t); go({ kind: "page", page: "portfolio", params: [t] }); };
  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <Dropdown aria-label="Account" value="Manual holdings" selectedOptions={["manual"]}>
          <Option value="manual">Manual holdings</Option>
        </Dropdown>
        <Caption1 style={{ color: "var(--dim)" }}>Paper trading and Schwab accounts arrive in a later update.</Caption1>
      </div>
      <TabList selectedValue={tab} onTabSelect={(_, d) => pick(d.value as PortfolioTab)}>
        {TABS.map(([t, label]) => <Tab key={t} value={t}>{label}</Tab>)}
      </TabList>
      {tab === "watchlists" ? <WatchlistsTab /> : <HoldingsTab />}
    </div>
  );
}
