import { Button, Dropdown, Option, OptionGroup, Tag, TagGroup } from "@fluentui/react-components";
import { lazy, Suspense, useMemo, useState } from "react";
import { useApi } from "../../lib/useApi";
import { api } from "../../lib/api";
import { barsFromSecurity, CHART_RANGES, DRAW_TOOLS, INDICATORS } from "../../lib/chart";
import { useSettings } from "../../lib/settings";
import Block from "../../blocks/Block";

const KlineChart = lazy(() => import("../../components/KlineChart"));

export default function ChartTab({ symbol }: { symbol: string }) {
  const { settings, update } = useSettings();
  const [range, setRange] = useState<string>((CHART_RANGES as readonly string[]).includes(settings.chartRange) ? settings.chartRange : "6mo");
  const [drawTool, setDrawTool] = useState<{ name: string; nonce: number } | null>(null);
  const sec = useApi(`chart:${symbol}:${range}`, () => api.security(symbol, range));
  const bars = useMemo(() => (sec.data ? barsFromSecurity(sec.data) : []), [sec.data]);
  const active = settings.indicators;
  const draw = (name: string) => setDrawTool({ name, nonce: Date.now() });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap", alignItems: "center" }}>
        {CHART_RANGES.map((r) => (
          <Button key={r} size="small" appearance={r === range ? "primary" : "subtle"} onClick={() => setRange(r)}>{r.toUpperCase()}</Button>
        ))}
        <span style={{ width: 12 }} />
        <Dropdown size="small" placeholder="+ Indicator" value="" selectedOptions={[]}
          onOptionSelect={(_, d) => d.optionValue && update({ indicators: [...active, d.optionValue] })}>
          <OptionGroup label="On price">
            {INDICATORS.filter((i) => i.main && !active.includes(i.name)).map((i) => <Option key={i.name} value={i.name}>{i.label}</Option>)}
          </OptionGroup>
          <OptionGroup label="Own pane">
            {INDICATORS.filter((i) => !i.main && !active.includes(i.name)).map((i) => <Option key={i.name} value={i.name}>{i.label}</Option>)}
          </OptionGroup>
        </Dropdown>
        <TagGroup onDismiss={(_, d) => update({ indicators: active.filter((n) => n !== d.value) })} aria-label="Active indicators">
          {active.map((n) => <Tag key={n} value={n} size="small" dismissible dismissIcon={{ "aria-label": `Remove ${n}` }}>{INDICATORS.find((i) => i.name === n)?.label ?? n}</Tag>)}
        </TagGroup>
      </div>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {DRAW_TOOLS.map(([name, label]) => <Button key={name} size="small" onClick={() => draw(name)}>{label}</Button>)}
        <Button size="small" appearance="subtle" onClick={() => draw("__clear__")}>Clear drawings</Button>
      </div>
      <Block fixed title={`${symbol} · ${range}`} loading={sec.loading} error={sec.error} fetchedAt={sec.fetchedAt}>
        {sec.data && (
          <Suspense fallback={<span style={{ color: "var(--dim)" }}>Loading chart…</span>}>
            <KlineChart bars={bars} indicators={active} drawTool={drawTool} />
          </Suspense>
        )}
      </Block>
    </div>
  );
}
