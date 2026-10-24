import { Tab, TabList } from "@fluentui/react-components";
import { useRoute } from "../lib/route";
import { readJson, writeJson } from "../lib/storage";
import ConsensusTab from "./smart/ConsensusTab";
import PlaceholderPage from "./PlaceholderPage";

export type SmartTab = "managers" | "consensus" | "insiders" | "history" | "search" | "funds";
export const SMART_TABS: [SmartTab, string][] = [
  ["managers", "Managers"], ["consensus", "Consensus"], ["insiders", "Insider buys"],
  ["history", "Position history"], ["search", "Filing search"], ["funds", "Funds"],
];
const KEY = "howlet_smart_tab_v1";
const isTab = (v: unknown): v is SmartTab => SMART_TABS.some(([t]) => t === v);

export function resolveSmartTab(params: string[] | undefined, saved: string | null): SmartTab {
  if (params?.[0] && isTab(params[0])) return params[0];
  return isTab(saved) ? saved : "managers";
}

export default function SmartMoneyPage({ params }: { params: string[] }) {
  const go = useRoute((r) => r.go);
  const tab = resolveSmartTab(params, readJson<string | null>(KEY, null, (v): v is string => typeof v === "string"));
  const pick = (t: SmartTab) => { writeJson(KEY, t); go({ kind: "page", page: "smart", params: [t] }); };
  const body = tab === "consensus" ? <ConsensusTab />
    : <PlaceholderPage title={SMART_TABS.find(([t]) => t === tab)![1]} />;
  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <TabList selectedValue={tab} onTabSelect={(_, d) => pick(d.value as SmartTab)}>
        {SMART_TABS.map(([t, label]) => <Tab key={t} value={t}>{label}</Tab>)}
      </TabList>
      {body}
    </div>
  );
}
