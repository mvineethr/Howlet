import { Button, CounterBadge, Popover, PopoverSurface, PopoverTrigger, Text, Link } from "@fluentui/react-components";
import { Alert24Regular, Dismiss16Regular } from "@fluentui/react-icons";
import { useCallback, useEffect, useState } from "react";
import { evaluate, getAlerts, removeAlert, saveAlerts, type PriceAlert } from "../lib/alerts";
import { api, type FilingAlert } from "../lib/api";
import { readJson, writeJson } from "../lib/storage";
import { useSettings } from "../lib/settings";
import { useRoute } from "../lib/route";

const SEEN_KEY = "howlet_seen_filings_v1"; // shared with the classic page
const isRecord = (v: unknown): v is Record<string, string> => !!v && typeof v === "object" && !Array.isArray(v);
const chime = () => {
  try { // 150 ms 880 Hz tone: no audio asset to ship
    const ctx = new AudioContext(), osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.frequency.value = 880; gain.gain.value = 0.05;
    osc.connect(gain); gain.connect(ctx.destination);
    osc.start(); osc.stop(ctx.currentTime + 0.15);
  } catch { /* audio blocked: the notification still shows */ }
};
const notify = (title: string, body: string) => {
  if ("Notification" in window && Notification.permission === "granted") new Notification(title, { body });
};

export default function AlertsBell() {
  const [alerts, setAlerts] = useState<PriceAlert[]>(getAlerts);
  const [newFilings, setNewFilings] = useState<FilingAlert[]>([]);
  const sound = useSettings((s) => s.settings.alertSound);
  const go = useRoute((r) => r.go);

  const pollPrices = useCallback(async () => {
    const current = getAlerts();
    const syms = [...new Set(current.filter((a) => !a.fired).map((a) => a.sym))];
    if (!syms.length) { setAlerts(current); return; }
    try {
      const rows = await api.quotes(syms);
      const prices = Object.fromEntries(rows.map((r) => [r.symbol.toUpperCase(), r.price]));
      const fired = evaluate(current, prices, new Date().toISOString());
      if (fired.length) {
        const byId = new Map(fired.map((f) => [f.id, f]));
        // Re-read so an alert added during the fetch is kept.
        saveAlerts(getAlerts().map((a) => byId.get(a.id) ?? a));
        fired.forEach((f) => notify(`${f.sym} ${f.op} ${f.px}`, `${f.sym} is at ${f.fired!.price.toFixed(2)}`));
        if (sound) chime();
      }
    } catch { /* market data is decoration: try again next tick */ }
    setAlerts(getAlerts());
  }, [sound]);

  const pollFilings = useCallback(async () => {
    let rows: FilingAlert[];
    try { rows = await api.filingAlerts(); } catch { return; }
    const seen = readJson<Record<string, string>>(SEEN_KEY, {}, isRecord);
    if (!Object.keys(seen).length) {
      rows.forEach((r) => { seen[r.cik] = r.accession_number; });
      writeJson(SEEN_KEY, seen); // first run: baseline silently
      return;
    }
    const fresh = rows.filter((r) => seen[r.cik] && seen[r.cik] !== r.accession_number);
    fresh.forEach((f) => notify(`New 13F filing: ${f.label.toUpperCase()}`, `Filed ${f.filing_date}`));
    setNewFilings(fresh);
  }, []);

  useEffect(() => {
    pollPrices(); pollFilings();
    const a = setInterval(pollPrices, 60_000), b = setInterval(pollFilings, 1_800_000);
    return () => { clearInterval(a); clearInterval(b); };
  }, [pollPrices, pollFilings]);

  const markSeen = () => {
    const seen = readJson<Record<string, string>>(SEEN_KEY, {}, isRecord);
    newFilings.forEach((f) => { seen[f.cik] = f.accession_number; });
    writeJson(SEEN_KEY, seen);
    saveAlerts(getAlerts().filter((a) => !a.fired));
    setNewFilings([]); setAlerts(getAlerts());
  };

  const count = alerts.filter((a) => a.fired).length + newFilings.length;
  return (
    <Popover onOpenChange={(_, d) => { if (d.open && "Notification" in window && Notification.permission === "default") Notification.requestPermission(); }}>
      <PopoverTrigger disableButtonEnhancement>
        <Button appearance="subtle" aria-label={`Alerts, ${count} new`} icon={
          <span style={{ position: "relative" }}><Alert24Regular />
            {count > 0 && <CounterBadge count={count} size="small" color="danger" style={{ position: "absolute", top: -6, right: -8 }} />}</span>} />
      </PopoverTrigger>
      <PopoverSurface style={{ width: 340 }}>
        <Text weight="semibold">Price alerts</Text>
        <Text block size={200} style={{ color: "var(--dim)" }}>Add with Ctrl+K: ALERT AAPL &gt; 350. Checked every minute while Howlet is open.</Text>
        {alerts.length === 0 && <Text block size={200}>None set.</Text>}
        {alerts.map((a) => (
          <div key={a.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "2px 0" }}>
            <Link onClick={() => go({ kind: "stock", symbol: a.sym, tab: "overview" })}>{a.sym}</Link>
            <span style={{ fontFamily: "var(--font-mono)" }}>{a.op} {a.px.toFixed(2)}</span>
            {a.fired ? <span style={{ color: "var(--up)" }}>hit {a.fired.price.toFixed(2)}</span> : <span style={{ color: "var(--dim)" }}>watching</span>}
            <Button size="small" appearance="subtle" icon={<Dismiss16Regular />} aria-label={`Remove ${a.sym} alert`}
              style={{ marginLeft: "auto" }} onClick={() => { removeAlert(a.id); setAlerts(getAlerts()); }} />
          </div>
        ))}
        <Text block weight="semibold" style={{ marginTop: 10 }}>New 13F filings</Text>
        {newFilings.length === 0
          ? <Text block size={200} style={{ color: "var(--dim)" }}>None since you last looked. Checked every 30 minutes.</Text>
          : newFilings.map((f) => <Text block key={f.accession_number}>{f.label.toUpperCase()} · filed {f.filing_date}</Text>)}
        {count > 0 && <Button size="small" style={{ marginTop: 10 }} onClick={markSeen}>Mark all seen</Button>}
      </PopoverSurface>
    </Popover>
  );
}
