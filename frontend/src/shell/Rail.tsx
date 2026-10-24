import { Tooltip, makeStyles, tokens } from "@fluentui/react-components";
import {
  Home24Regular, ArrowTrending24Regular, PeopleTeam24Regular, Filter24Regular,
  News24Regular, Briefcase24Regular, Settings24Regular,
} from "@fluentui/react-icons";
import type { JSX } from "react";
import { useSettings, type PageId } from "../lib/settings";
import { useRoute, visibleRail } from "../lib/route";

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
  rail: {
    width: "56px", display: "flex", flexDirection: "column", alignItems: "center", gap: "4px",
    paddingTop: "8px", backgroundColor: tokens.colorNeutralBackground1,
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  item: {
    width: "40px", height: "36px", display: "flex", alignItems: "center", justifyContent: "center",
    borderRadius: tokens.borderRadiusMedium, border: "none", background: "transparent",
    color: tokens.colorNeutralForeground3, cursor: "pointer",
    ":hover": { backgroundColor: tokens.colorNeutralBackground3 },
  },
  on: { color: tokens.colorBrandForeground1, backgroundColor: tokens.colorNeutralBackground3, boxShadow: `inset 3px 0 0 ${tokens.colorBrandForeground1}` },
  bottom: { marginTop: "auto", marginBottom: "8px" },
});

export default function Rail() {
  const s = useStyles();
  const settings = useSettings((st) => st.settings);
  const { route, go } = useRoute();
  const pages = visibleRail(settings).filter((p) => p !== "settings");
  const item = (p: PageId, extra = "") => {
    const on = route.kind === "page" && route.page === p;
    return (
      <Tooltip key={p} content={PAGE_META[p].label} relationship="label" positioning="after">
        <button className={`${s.item} ${on ? s.on : ""} ${extra}`} aria-current={on ? "page" : undefined}
          onClick={() => go({ kind: "page", page: p })}>{PAGE_META[p].icon}</button>
      </Tooltip>
    );
  };
  return <nav className={s.rail} aria-label="Pages">{pages.map((p) => item(p))}{item("settings", s.bottom)}</nav>;
}
