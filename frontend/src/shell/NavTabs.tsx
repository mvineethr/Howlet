import { makeStyles, tokens } from "@fluentui/react-components";
import {
  Home24Regular, ArrowTrending24Regular, PeopleTeam24Regular, Filter24Regular,
  News24Regular, Briefcase24Regular, Settings24Regular,
} from "@fluentui/react-icons";
import type { JSX } from "react";
import { useSettings, type PageId } from "../lib/settings";
import { useRoute, visibleRail } from "../lib/route";

// Page labels and icons. Icons are still used by Settings (tab order list);
// the tab bar itself is plain text, matching the Trading Research Space.
export const PAGE_META: Record<PageId, { label: string; icon: JSX.Element }> = {
  home: { label: "Home", icon: <Home24Regular /> },
  markets: { label: "Markets", icon: <ArrowTrending24Regular /> },
  smart: { label: "Smart Money", icon: <PeopleTeam24Regular /> },
  screener: { label: "Screener", icon: <Filter24Regular /> },
  news: { label: "News", icon: <News24Regular /> },
  portfolio: { label: "Portfolio", icon: <Briefcase24Regular /> },
  settings: { label: "Settings", icon: <Settings24Regular /> },
};

const useStyles = makeStyles({
  bar: {
    display: "flex", alignItems: "stretch", gap: "4px", padding: "0 16px",
    backgroundColor: tokens.colorNeutralBackground1,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  item: {
    display: "flex", alignItems: "center", padding: "10px 10px 8px",
    border: "none", borderBottom: "2px solid transparent", background: "transparent",
    color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase300,
    cursor: "pointer", whiteSpace: "nowrap",
    ":hover": { color: tokens.colorNeutralForeground1 },
  },
  on: {
    color: tokens.colorNeutralForeground1, fontWeight: tokens.fontWeightSemibold,
    borderBottomColor: tokens.colorNeutralForeground1,
  },
});

export default function NavTabs() {
  const s = useStyles();
  const settings = useSettings((st) => st.settings);
  const { route, go } = useRoute();
  const pages = visibleRail(settings).filter((p) => p !== "settings");
  const item = (p: PageId) => {
    const on = route.kind === "page" && route.page === p;
    return (
      <button key={p} className={`${s.item} ${on ? s.on : ""}`} aria-current={on ? "page" : undefined}
        onClick={() => go({ kind: "page", page: p })}>{PAGE_META[p].label}</button>
    );
  };
  return <nav className={s.bar} aria-label="Pages">{pages.map((p) => item(p))}{item("settings")}</nav>;
}
