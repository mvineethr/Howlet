import { useEffect, useState } from "react";
import { Button, Dropdown, Input, Option } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type Events, type Quote } from "../../lib/api";
import { getWatchlists } from "../../lib/legacy";
import { REFRESH_MS, useSettings } from "../../lib/settings";
import { fmtInt, fmtNum, signed, tone } from "../../lib/fmt";
import { addSymbol, createList, deleteList, removeSymbol, saveWatchlists, type Watchlists } from "../../lib/watchlists";
import Block from "../../blocks/Block";
import DataTable, { type Column } from "../../components/DataTable";
import Ticker from "../../components/Ticker";
import Sparkline from "../../components/Sparkline";
import NewsList from "../../components/NewsList";
import { stockSymbols } from "../smart/InsiderBuysTab";

const FIVE_MIN = 300_000;
const num = (s: string, color?: string) => <span className="num" style={color ? { color } : undefined}>{s}</span>;
// Shared across mounts: events lookups hit throttled SEC proxy pages, so never refetch within a session.
const eventsCache = new Map<string, Events | "error">();

type QRow = { s: string; q: Quote | undefined };
type EvRow = { s: string; e: Events | "error" };

export default function WatchlistsTab() {
  const refreshMs = REFRESH_MS[useSettings((s) => s.settings.refresh)];
  const [all, setAll] = useState<Watchlists>(getWatchlists);
  const [list, setList] = useState(() => ("default" in all ? "default" : Object.keys(all)[0]));
  const [sym, setSym] = useState("");
  const [newName, setNewName] = useState("");
  const [err, setErr] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [, setTick] = useState(0);

  const symbols = all[list] ?? [];
  const stocks = stockSymbols(symbols);
  const evSyms = stocks.slice(0, 12);
  const evKey = evSyms.join(",");
  const newsSyms = stocks.slice(0, 10);
  const commit = (next: Watchlists) => { setAll(next); saveWatchlists(next); };

  const quotes = useApi(symbols.length ? `pf-wl:${list}:${symbols.join(",")}` : null, () => api.quotes(symbols), refreshMs);
  const news = useApi(newsSyms.length ? `pf-news:${newsSyms.join(",")}` : null, () => api.newsFor(newsSyms, 40), FIVE_MIN);

  // Sequential on purpose: each lookup can trigger throttled SEC requests.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      for (const s of evKey ? evKey.split(",") : []) {
        if (cancelled) break;
        if (!eventsCache.has(s)) {
          try { eventsCache.set(s, await api.events(s)); } catch { eventsCache.set(s, "error"); }
        }
        setTick((t) => t + 1);
      }
    })();
    return () => { cancelled = true; };
  }, [evKey]);

  const add = () => { commit(addSymbol(all, list, sym)); setSym(""); };
  const create = () => {
    const r = createList(all, newName);
    if ("error" in r) { setErr(r.error); return; }
    setErr(""); setNewName(""); setConfirm(false); commit(r.all); setList(r.name);
  };
  const del = () => {
    if (!confirm) { setConfirm(true); return; }
    const next = deleteList(all, list);
    setConfirm(false); commit(next); setList(Object.keys(next)[0]);
  };

  const bySym = new Map((quotes.data ?? []).map((q) => [q.symbol, q]));
  const rows: QRow[] = symbols.map((s) => ({ s, q: bySym.get(s) }));
  const cols: Column<QRow>[] = [
    { key: "x", label: "", render: (r) => <Button size="small" appearance="subtle" aria-label={`Remove ${r.s}`} onClick={() => commit(removeSymbol(all, list, r.s))}>✕</Button> },
    { key: "s", label: "Symbol", render: (r) => <Ticker symbol={r.s} /> },
    { key: "n", label: "Name", render: (r) => <span style={{ color: "var(--dim)" }}>{r.q ? r.q.name ?? "" : quotes.data ? "no data" : ""}</span> },
    { key: "p", label: "Price", align: "right", render: (r) => num(r.q ? fmtNum(r.q.price) : "—") },
    { key: "c", label: "%Chg", align: "right", render: (r) => num(r.q?.change_pct == null ? "—" : `${signed(r.q.change_pct)}%`, tone(r.q?.change_pct)) },
    { key: "w", label: "5D", render: (r) => <Sparkline values={r.q?.sparkline} w={70} h={14} /> },
    { key: "r", label: "Day range", render: (r) => num(r.q?.day_low == null || r.q.day_high == null ? "—" : `${fmtNum(r.q.day_low)} – ${fmtNum(r.q.day_high)}`) },
    { key: "v", label: "Volume", align: "right", render: (r) => num(fmtInt(r.q?.volume)) },
  ];

  const evRows: EvRow[] = [];
  for (const s of evSyms) { const e = eventsCache.get(s); if (e) evRows.push({ s, e }); }
  const evCell = (r: EvRow, pick: (e: Events) => string) =>
    r.e === "error" ? <span style={{ color: "var(--dim)" }}>unavailable</span> : num(pick(r.e));
  const evCols: Column<EvRow>[] = [
    { key: "s", label: "Symbol", render: (r) => <Ticker symbol={r.s} /> },
    { key: "e", label: "Next earnings", render: (r) => evCell(r, (e) => e.next_earnings_date ?? "—") },
    { key: "a", label: "Analysts", render: (r) => (r.e === "error" ? null : num(r.e.analyst_recommendation ?? "—")) },
    { key: "p", label: "Last proxy", render: (r) => (r.e === "error" ? null : num(r.e.shareholder_meetings[0] ? `DEF 14A ${r.e.shareholder_meetings[0].filing_date}` : "—")) },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        <Dropdown aria-label="Watchlist" value={list} selectedOptions={[list]}
          onOptionSelect={(_, d) => { if (d.optionValue) { setList(d.optionValue); setConfirm(false); } }}>
          {Object.keys(all).map((n) => <Option key={n} value={n}>{n}</Option>)}
        </Dropdown>
        <Input aria-label="New list" placeholder="New list" value={newName} onChange={(_, d) => setNewName(d.value)}
          onKeyDown={(e) => { if (e.key === "Enter") create(); }} />
        <Button onClick={create}>Create</Button>
        <Button disabled={Object.keys(all).length <= 1} onClick={del}>{confirm ? "Confirm delete" : "Delete list"}</Button>
        <Input aria-label="Add symbol" placeholder="Add symbol" value={sym} onChange={(_, d) => setSym(d.value)}
          onKeyDown={(e) => { if (e.key === "Enter") add(); }} />
        <Button appearance="primary" onClick={add}>Add</Button>
        {err && <span role="alert" style={{ color: "var(--down)" }}>{err}</span>}
      </div>
      <Block fixed title={`Quotes · ${list}`} loading={quotes.loading} error={quotes.error} fetchedAt={quotes.fetchedAt} refreshMs={refreshMs}>
        <DataTable columns={cols} rows={rows} rowKey={(r) => r.s} empty="Empty list — add a symbol above." />
      </Block>
      <Block fixed title="News" loading={news.loading} error={news.error} fetchedAt={news.fetchedAt} refreshMs={FIVE_MIN}>
        {newsSyms.length ? news.data && <NewsList items={news.data} empty="No headlines right now." />
          : <span style={{ color: "var(--dim)" }}>Add stock symbols to see scoped news.</span>}
      </Block>
      <Block fixed title="Upcoming events">
        <DataTable columns={evCols} rows={evRows} rowKey={(r) => r.s}
          empty={evSyms.length ? "Loading events…" : "Add stock symbols to see events."} />
      </Block>
    </div>
  );
}
