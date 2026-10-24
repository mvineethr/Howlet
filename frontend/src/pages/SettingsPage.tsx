import {
  Button, Card, Dropdown, Field, Option, Radio, RadioGroup, Switch, Text, Title3, Subtitle2,
} from "@fluentui/react-components";
import { ArrowUp16Regular, ArrowDown16Regular } from "@fluentui/react-icons";
import { useRef, useState } from "react";
import { useSettings, PAGE_IDS, type PageId, type Settings } from "../lib/settings";
import { PAGE_META } from "../shell/Rail";
import { HOME_KEY } from "../lib/legacy";
import { writeJson } from "../lib/storage";
import { firstRunHome } from "../blocks/registry";
import { ACCENT_SWATCHES } from "../theme/tokens";

const RANGES = ["1mo", "3mo", "6mo", "1y", "5y"];
const SHORTCUTS: [string, string][] = [["Ctrl+K", "Search or command"], ["Ctrl+1 … Ctrl+7", "Jump to rail page"], ["Esc", "Close / clear"], ["Alt+←", "Back"]];

export default function SettingsPage() {
  const { settings: s, update } = useSettings();
  const [msg, setMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const set = <K extends keyof Settings>(k: K) => (v: Settings[K]) => update({ [k]: v } as Partial<Settings>);

  const move = (p: PageId, dir: -1 | 1) => {
    const order = [...s.railOrder];
    const i = order.indexOf(p), j = i + dir;
    if (j < 0 || j >= order.length) return;
    [order[i], order[j]] = [order[j], order[i]];
    update({ railOrder: order });
  };

  const exportState = () => {
    const data: Record<string, string> = {};
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)!;
      if (k.startsWith("howlet_")) data[k] = localStorage.getItem(k)!;
    }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    a.download = `howlet-backup-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
  };
  const importState = async (f: File) => {
    try {
      const data = JSON.parse(await f.text());
      if (!data || typeof data !== "object") throw new Error("not an object");
      let n = 0;
      for (const [k, v] of Object.entries(data)) if (k.startsWith("howlet_") && typeof v === "string") { localStorage.setItem(k, v); n++; }
      setMsg(`Imported ${n} items. Reloading…`);
      setTimeout(() => location.reload(), 600);
    } catch { setMsg("That file isn't a Howlet backup."); }
  };

  return (
    <div style={{ padding: 16, display: "grid", gap: 12, maxWidth: 760 }}>
      <Title3>Settings</Title3>

      <Card><Subtitle2>Appearance</Subtitle2>
        <Field label="Theme"><RadioGroup layout="horizontal" value={s.themeMode} onChange={(_, d) => set("themeMode")(d.value as Settings["themeMode"])}>
          <Radio value="system" label="Follow Windows" /><Radio value="light" label="Light" /><Radio value="dark" label="Dark" />
        </RadioGroup></Field>
        <Field label="Accent colour"><div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {ACCENT_SWATCHES.map((c) => (
            <button key={c} aria-label={`Accent ${c}`} aria-pressed={s.accent === c} onClick={() => set("accent")(c)}
              style={{ width: 24, height: 24, borderRadius: 12, background: c, cursor: "pointer",
                border: s.accent === c ? "2px solid var(--text)" : "2px solid transparent" }} />
          ))}
          <input type="color" aria-label="Custom accent colour" value={s.accent} onChange={(e) => set("accent")(e.target.value)} />
        </div></Field>
        <Field label="Density"><RadioGroup layout="horizontal" value={s.density} onChange={(_, d) => set("density")(d.value as Settings["density"])}>
          <Radio value="comfortable" label="Comfortable" /><Radio value="compact" label="Compact" />
        </RadioGroup></Field>
        <Field label="Text size"><RadioGroup layout="horizontal" value={s.textSize} onChange={(_, d) => set("textSize")(d.value as Settings["textSize"])}>
          <Radio value="small" label="Small" /><Radio value="medium" label="Medium" /><Radio value="large" label="Large" />
        </RadioGroup></Field>
      </Card>

      <Card><Subtitle2>Rail</Subtitle2>
        {s.railOrder.map((p, i) => {
          const locked = p === "home" || p === "settings";
          return (
            <div key={p} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {PAGE_META[p].icon}<Text style={{ flex: 1 }}>{PAGE_META[p].label}</Text>
              <Button size="small" appearance="subtle" icon={<ArrowUp16Regular />} aria-label={`Move ${PAGE_META[p].label} up`} disabled={i === 0} onClick={() => move(p, -1)} />
              <Button size="small" appearance="subtle" icon={<ArrowDown16Regular />} aria-label={`Move ${PAGE_META[p].label} down`} disabled={i === s.railOrder.length - 1} onClick={() => move(p, 1)} />
              <Switch aria-label={`Show ${PAGE_META[p].label}`} checked={!s.railHidden.includes(p)} disabled={locked}
                onChange={(_, d) => update({ railHidden: d.checked ? s.railHidden.filter((x) => x !== p) : [...s.railHidden, p] })} />
            </div>
          );
        })}
      </Card>

      <Card><Subtitle2>Defaults</Subtitle2>
        <Field label="Start page"><Dropdown value={PAGE_META[s.startPage].label} selectedOptions={[s.startPage]}
          onOptionSelect={(_, d) => set("startPage")(d.optionValue as PageId)}>
          {PAGE_IDS.map((p) => <Option key={p} value={p}>{PAGE_META[p].label}</Option>)}
        </Dropdown></Field>
        <Field label="Default chart range"><Dropdown value={s.chartRange} selectedOptions={[s.chartRange]} onOptionSelect={(_, d) => set("chartRange")(d.optionValue!)}>
          {RANGES.map((r) => <Option key={r} value={r}>{r}</Option>)}
        </Dropdown></Field>
        <Field label="Refresh speed (prices, news, crypto)"><RadioGroup layout="horizontal" value={s.refresh} onChange={(_, d) => set("refresh")(d.value as Settings["refresh"])}>
          <Radio value="fast" label="Fast (15s)" /><Radio value="normal" label="Normal (1 min)" /><Radio value="slow" label="Slow (5 min)" />
        </RadioGroup></Field>
        <Switch label="Alert sound" checked={s.alertSound} onChange={(_, d) => set("alertSound")(d.checked)} />
        <Switch label="Show Options tab (experimental)" checked={s.showOptions} onChange={(_, d) => set("showOptions")(d.checked)} />
      </Card>

      <Card><Subtitle2>Layouts &amp; backup</Subtitle2>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Button onClick={() => { writeJson(HOME_KEY, firstRunHome()); setMsg("Home reset to the default 4 blocks."); }}>Restore default Home</Button>
          <Button onClick={exportState}>Export backup</Button>
          <Button onClick={() => fileRef.current?.click()}>Import backup</Button>
          <input ref={fileRef} type="file" accept="application/json" hidden onChange={(e) => e.target.files?.[0] && importState(e.target.files[0])} />
        </div>
        {msg && <Text role="status">{msg}</Text>}
      </Card>

      <Card><Subtitle2>Keyboard shortcuts</Subtitle2>
        {SHORTCUTS.map(([k, v]) => <div key={k} style={{ display: "flex", gap: 12 }}><code style={{ minWidth: 140 }}>{k}</code><Text>{v}</Text></div>)}
      </Card>
    </div>
  );
}
