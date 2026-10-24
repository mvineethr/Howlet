import { Tab, TabList } from "@fluentui/react-components";
import { useState } from "react";
import { readJson, writeJson } from "../lib/storage";
import StocksTab from "./markets/StocksTab";
import CryptoTab from "./markets/CryptoTab";
import FxTab from "./markets/FxTab";
import EconomyTab from "./markets/EconomyTab";

export type MarketsTab = "stocks" | "crypto" | "fx" | "economy";
const TABS: [MarketsTab, string][] = [["stocks", "Stocks"], ["crypto", "Crypto"], ["fx", "FX"], ["economy", "Economy"]];
export const MARKETS_TAB_KEY = "howlet_markets_tab_v1";
const isTab = (v: unknown): v is MarketsTab => TABS.some(([t]) => t === v);

export function initialMarketsTab(): MarketsTab {
  const saved = readJson<MarketsTab | null>(MARKETS_TAB_KEY, null, (v): v is MarketsTab => isTab(v));
  if (saved) return saved;
  let legacy: string | null = null;
  try { legacy = localStorage.getItem("howlet_mkts_mode"); } catch { /* storage blocked */ }
  return legacy === "crypto" ? "crypto" : "stocks";
}

export default function MarketsPage() {
  const [tab, setTab] = useState<MarketsTab>(initialMarketsTab);
  const pick = (t: MarketsTab) => { setTab(t); writeJson(MARKETS_TAB_KEY, t); };
  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <TabList selectedValue={tab} onTabSelect={(_, d) => pick(d.value as MarketsTab)}>
        {TABS.map(([t, label]) => <Tab key={t} value={t}>{label}</Tab>)}
      </TabList>
      {tab === "stocks" && <StocksTab />}
      {tab === "crypto" && <CryptoTab />}
      {tab === "fx" && <FxTab />}
      {tab === "economy" && <EconomyTab />}
    </div>
  );
}
