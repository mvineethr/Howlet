import { FluentProvider } from "@fluentui/react-components";
import { useEffect, useMemo, useState } from "react";
import { buildTheme, resolveMode, applyCssVars } from "./theme/theme";
import { useSettings } from "./lib/settings";
import { useRoute, visibleRail } from "./lib/route";
import Rail, { PAGE_META } from "./shell/Rail";
import TopBar from "./shell/TopBar";
import CommandBox from "./shell/CommandBox";
import AlertsBell from "./shell/AlertsBell";
import PlaceholderPage from "./pages/PlaceholderPage";
import StockPage from "./pages/StockPage";
import HomePage from "./pages/HomePage";
import SettingsPage from "./pages/SettingsPage";

const prefersDark = () => window.matchMedia("(prefers-color-scheme: dark)").matches;
const TEXT_SCALE = { small: "13px", medium: "14px", large: "16px" } as const;

export default function App() {
  const settings = useSettings((s) => s.settings);
  const { route, go } = useRoute();
  const [osDark, setOsDark] = useState(prefersDark);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const on = () => setOsDark(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  const dark = resolveMode(settings.themeMode, osDark) === "dark";
  const theme = useMemo(() => buildTheme(dark, settings.accent), [dark, settings.accent]);
  useEffect(() => applyCssVars(dark, settings.accent), [dark, settings.accent]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.ctrlKey || e.altKey || e.metaKey) return;
      const n = Number(e.key);
      const rail = visibleRail(settings);
      if (n >= 1 && n <= rail.length) { e.preventDefault(); go({ kind: "page", page: rail[n - 1] }); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [settings, go]);

  const page = route.kind === "stock"
    ? <StockPage symbol={route.symbol} tab={route.tab} />
    : route.page === "home" ? <HomePage /> : route.page === "settings" ? <SettingsPage /> : <PlaceholderPage title={PAGE_META[route.page].label} />;

  return (
    <FluentProvider theme={theme} style={{ height: "100vh", display: "flex", flexDirection: "column", fontSize: TEXT_SCALE[settings.textSize] }}
      data-density={settings.density}>
      <TopBar center={<CommandBox />} right={<AlertsBell />} />
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        <Rail />
        <main style={{ flex: 1, overflow: "auto", background: "var(--bg)" }}>{page}</main>
      </div>
    </FluentProvider>
  );
}
