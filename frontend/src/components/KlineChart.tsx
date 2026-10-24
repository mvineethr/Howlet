import { useEffect, useRef } from "react";
import { dispose, init, type Chart, type KLineData, type DeepPartial, type Styles } from "klinecharts";
import { chartStyles, MAIN_PANE, type Bar } from "../lib/chart";
import { useSettings } from "../lib/settings";

const readVar = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const applyTheme = (c: Chart) => c.setStyles(chartStyles(readVar) as DeepPartial<Styles>);

type Props = { bars: Bar[]; indicators: string[]; drawTool: { name: string; nonce: number } | null };

export default function KlineChart({ bars, indicators, drawTool }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<Chart | null>(null);
  const panes = useRef(new Map<string, string>()); // indicator name -> pane id
  const { themeMode, accent } = useSettings((s) => s.settings);

  useEffect(() => {
    const node = el.current!;
    const c = init(node);
    chart.current = c;
    if (c) applyTheme(c);
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => c?.resize()) : null;
    ro?.observe(node);
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const onScheme = () => c && requestAnimationFrame(() => applyTheme(c));
    mq?.addEventListener("change", onScheme);
    return () => { ro?.disconnect(); mq?.removeEventListener("change", onScheme); panes.current.clear(); dispose(node); chart.current = null; };
  }, []);

  // CSS vars are rewritten by App's effect; re-read them after it runs.
  useEffect(() => { const c = chart.current; if (c) requestAnimationFrame(() => applyTheme(c)); }, [themeMode, accent]);

  useEffect(() => { chart.current?.applyNewData(bars as KLineData[]); }, [bars]);

  useEffect(() => {
    const c = chart.current;
    if (!c) return;
    for (const [name, paneId] of [...panes.current]) {
      if (!indicators.includes(name)) { c.removeIndicator(paneId, name); panes.current.delete(name); }
    }
    for (const name of indicators) {
      if (panes.current.has(name)) continue;
      const main = MAIN_PANE.includes(name);
      const paneId = main ? c.createIndicator(name, true, { id: "candle_pane" }) : c.createIndicator(name);
      if (paneId) panes.current.set(name, paneId);
    }
  }, [indicators]);

  useEffect(() => {
    const c = chart.current;
    if (!c || !drawTool) return;
    if (drawTool.name === "__clear__") c.removeOverlay(); else c.createOverlay(drawTool.name);
  }, [drawTool]);

  return <div ref={el} style={{ width: "100%", height: 460 }} />;
}
