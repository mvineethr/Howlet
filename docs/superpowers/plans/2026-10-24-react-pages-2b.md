# Howlet React pages 2b: stock page tabs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the stock page: Overview gains earnings/analyst events and studies + ORB; the Chart (KLineChart with ranges, indicators, drawing tools), Financials, Holders (13F holders, Form 4 insiders, SEC filings), News and Options tabs replace their placeholders.

**Architecture:** Part 2 of 4 of the redesign's plan 2 (2a shipped News/Markets/Screener). Classic reference: `docs/superpowers/plans/classic-inventory.md` §2 (DES/FA/HDS/chart), §9 (OPT), widgets 7 (insiders) and 15 (filings). KLineChart comes from npm pinned to **9.8.12** — the exact version vendored at `src/howlet/static/klinecharts.min.js` — and is lazy-loaded so it only ships when the Chart tab opens. No Python changes.

**Tech Stack:** React 18, TypeScript, Vite 5, Fluent UI v9, zustand, Vitest; `klinecharts@9.8.12` (Apache-2.0).

## Global Constraints

- No change to `views.py`, the MCP server, the CLI, any `/api/*` route, or `src/howlet/dashboard.html`.
- Colour hex literals only in `frontend/src/theme/tokens.ts`. The chart theme reads CSS variables at runtime (`getComputedStyle(document.documentElement)`), never restates colours (CLAUDE.md gotcha "KLineChart's theme is a SECOND copy of the palette").
- `klinecharts` must be pinned exactly: `"klinecharts": "9.8.12"` (no caret).
- Numbers use the `.num` class; up/down/dim via `tone()` / `var(--up|--down|--dim)`.
- Date-only strings (`next_earnings_date`, `filing_date`, `period_of_report`, `end_date`, Form 4 `date`) are shown raw — never through `new Date(...)`.
- External links only via `safeHref` (http/https), `target="_blank" rel="noopener noreferrer"`.
- Market/Yahoo-backed panels (quote, chart, events, options, news) degrade quietly via `Block`; SEC-backed panels (financials, holders, insiders, filings) use `sec` so the server's error text shows.
- Each tab fetches only when it is shown; one failing panel never blanks another.
- `/api/holders` is slow (≈2 min cold, ≈40 s warm): requests for the same symbol must be shared (one in-flight request, 10-minute memo) between the 🦉 chips and the Holders tab.
- Run frontend commands from `frontend/`; build with `npm run build` and commit `src/howlet/static/app` (stage with `git add -A src/howlet/static/app`) in every task that changes UI. Verify live at `http://localhost:8813/`.

## File structure

```
frontend/src/
  lib/api.ts                    # + security(symbol, range), events, facts, insiders, filings, options, newsFor; holders memoised
  lib/chart.ts                  # pure: CHART_RANGES, MAIN_PANE, INDICATORS, barsFromSecurity, chartStyles
  components/KlineChart.tsx     # the only file that imports "klinecharts"; lazy-loaded
  pages/stock/OverviewTab.tsx   # stats + events + studies/ORB
  pages/stock/ChartTab.tsx      # ranges, indicator picker/chips, drawing tools, <KlineChart>
  pages/stock/FinancialsTab.tsx
  pages/stock/HoldersTab.tsx    # 13F holders + insiders + filings
  pages/stock/NewsTab.tsx
  pages/stock/OptionsTab.tsx
  pages/StockPage.tsx           # header + chips + tab switch only
  App.tsx                       # page switch becomes a lookup map
```

---

### Task 1: API additions, holders memo, Overview tab

**Files:**
- Modify: `frontend/src/lib/api.ts`, `frontend/src/pages/StockPage.tsx`
- Create: `frontend/src/pages/stock/OverviewTab.tsx`
- Test: `frontend/src/lib/api.holders.test.ts`, `frontend/src/pages/stock/OverviewTab.test.tsx`

**Interfaces:**
- Consumes: `getJson`, `Quote`, `Security`, `NewsItem`, `HoldersResult` (`api.ts`); `useApi`; `Block` (`fixed`, `sec`, `actions`); `DataTable`; `fmtNum`, `fmtInt`, `signed`, `tone`; `useSettings`, `REFRESH_MS`.
- Produces in `api.ts` (field names verified live 2026-10-24):
```ts
export type Studies = Partial<Record<"sma20" | "sma50" | "ema12" | "ema26" | "rsi14" | "macd" | "macd_signal" |
  "macd_histogram" | "bollinger_upper" | "bollinger_mid" | "bollinger_lower", number | null>>;
export type Orb = { range_high: number; range_low: number; last_price: number; status: "ABOVE_RANGE" | "BELOW_RANGE" | "INSIDE_RANGE"; breakout_pct: number };
export type SecurityDetail = Security & {
  currency: string | null; range: string; range_change_pct: number | null;
  history_ts: number[]; history_open: number[]; history_high: number[]; history_low: number[];
  history_close: number[]; history_volume: number[]; studies: Studies; orb: Orb | null;
};
export type Events = {
  symbol: string; next_earnings_date: string | null; analyst_recommendation: string | null;
  analyst_counts: { strong_buy: number; buy: number; hold: number; sell: number; strong_sell: number } | null;
  shareholder_meetings: { form: string; filing_date: string; accession_number: string; primary_doc?: string }[];
};
export type FiscalYear = { fiscal_year: number; end_date: string; revenue: number | null; net_income: number | null;
  eps_diluted: number | null; total_assets: number | null; total_liabilities: number | null;
  stockholders_equity: number | null; operating_cash_flow: number | null };
export type Facts = { symbol: string; cik: string; company: string; fiscal_years: FiscalYear[] };
export type InsiderTxn = { insider: string; relationship: string | null; date: string | null; code: string; code_label: string;
  shares: number | null; price_per_share: number | null; value_usd: number | null; filing_date: string; accession_number: string };
export type Insiders = { symbol: string; company: string; filings_scanned: number;
  summary: { open_market_purchases: number; purchase_value_usd: number; open_market_sales: number; sale_value_usd: number };
  transactions: InsiderTxn[] };
export type Filing = { form: string | null; filing_date: string; period_of_report: string | null; accession_number: string; url: string };
export type Filings = { symbol: string; company: string; filings: Filing[] };
export type OptionContract = { contract_symbol: string; strike: number; last_price: number | null; bid: number | null; ask: number | null;
  volume: number | null; open_interest: number | null; implied_volatility: number | null; in_the_money: boolean };
export type OptionsChain = { symbol: string; underlying_price: number | null; expiration_dates: string[];
  selected_expiration: string | null; calls: OptionContract[]; puts: OptionContract[] };
```
  In the `api` object: `security` gains an optional range — `security: (symbol: string, range?: string) => getJson<SecurityDetail>(\`/api/security/${q(symbol)}${range ? \`?range=${q(range)}\` : ""}\`)`; plus
```ts
  events: (s: string) => getJson<Events>(`/api/events/${q(s)}`),
  facts: (s: string) => getJson<Facts>(`/api/facts/${q(s)}`),
  insiders: (s: string, filings = 15) => getJson<Insiders>(`/api/insiders/${q(s)}?filings=${filings}`),
  filings: (s: string, limit = 15) => getJson<Filings>(`/api/filings/${q(s)}?limit=${limit}`),
  options: (s: string, expiration?: string) => getJson<OptionsChain>(`/api/options/${q(s)}${expiration ? `?expiration=${q(expiration)}` : ""}`),
  newsFor: (symbols: string[], limit = 15) => getJson<NewsItem[]>(`/api/news?limit=${limit}&symbols=${q(symbols.join(","))}`),
```
  and `holders` becomes memoised: a module-level `Map<string, { at: number; p: Promise<HoldersResult> }>`; a call within 10 minutes of the last for the same upper-cased symbol returns the same promise (in-flight or settled); a rejected promise is evicted so the next call retries. Export `clearHoldersMemo()` for tests.
- `OverviewTab({ symbol, q })` where `q: SecurityDetail | undefined` (the page's existing quote) renders three `Block fixed` panels in a `repeat(auto-fit, minmax(300px, 1fr))` grid:
  1. **Quote** — the six stats already on the page plus "Range change ({range})" = `signed(range_change_pct)%` toned, "Type" `instrument_type`, "Exchange", "Currency".
  2. **Events** (`api.events`, no refresh) — "Next earnings" (`next_earnings_date` raw, else "unknown"), "Analysts" (`analyst_recommendation`, else "n/a"), counts line "Strong buy N · Buy N · Hold N · Sell N · Strong sell N" when `analyst_counts` is non-null, then up to 5 `shareholder_meetings` as "`form` · `filing_date`"; none → "None on file.".
  3. **Studies** — from `q.studies` rows: SMA 20, SMA 50, EMA 12, EMA 26, RSI 14, MACD, MACD signal, MACD hist, Bollinger upper/mid/lower (`fmtNum`, "—" for null). Empty studies object → "Not enough history to compute studies at this range.". Then ORB: `orb == null` → "ORB unavailable (needs today's intraday bars — try during market hours)."; else a status badge (`status.replace("_", " ")`; success for ABOVE_RANGE, danger for BELOW_RANGE, informative for INSIDE_RANGE), "Range" `fmtNum(range_low) – fmtNum(range_high)`, "Breakout" "—" when `breakout_pct === 0` else `signed(breakout_pct)%` toned.
- `StockPage` keeps its header + chips + tab list; the Overview branch renders `<OverviewTab symbol={symbol} q={q} />` (its `useApi` key/fetcher stay `sec:${symbol}` / `api.security(symbol)`); other tabs keep `PlaceholderPage` until their tasks.

- [ ] **Step 1: Write the failing tests**

`frontend/src/lib/api.holders.test.ts`:
```ts
import { api, clearHoldersMemo } from "./api";

afterEach(() => { vi.restoreAllMocks(); clearHoldersMemo(); });
const body = { symbol: "AAPL", tracked_managers: [], holders: [] };

test("concurrent and repeat calls share one request", async () => {
  const f = vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(new Response(JSON.stringify(body))));
  const [a, b] = await Promise.all([api.holders("AAPL"), api.holders("aapl")]);
  await api.holders("AAPL");
  expect(a).toEqual(body);
  expect(b).toBe(a);
  expect(f).toHaveBeenCalledTimes(1);
});

test("a failure is not memoised", async () => {
  const f = vi.spyOn(globalThis, "fetch")
    .mockImplementationOnce(() => Promise.resolve(new Response("{}", { status: 502 })))
    .mockImplementation(() => Promise.resolve(new Response(JSON.stringify(body))));
  await expect(api.holders("MSFT")).rejects.toBeTruthy();
  await expect(api.holders("MSFT")).resolves.toEqual(body);
  expect(f).toHaveBeenCalledTimes(2);
});
```

`frontend/src/pages/stock/OverviewTab.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import OverviewTab from "./OverviewTab";
import type { SecurityDetail } from "../../lib/api";

afterEach(() => vi.restoreAllMocks());

const q = {
  symbol: "AAPL", name: "Apple Inc.", price: 100, change: 1, change_pct: 1, previous_close: 99, currency: "USD",
  day_low: 98, day_high: 101, week52_low: 80, week52_high: 120, volume: 1000, exchange: "NasdaqGS",
  instrument_type: "EQUITY", range: "6mo", range_change_pct: -2.5, history_ts: [], history_open: [], history_high: [],
  history_low: [], history_close: [], history_volume: [], studies: { sma20: 101.234, sma50: null }, orb: null,
} as unknown as SecurityDetail;

test("quote, studies, ORB-unavailable and events render; dates stay raw", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    symbol: "AAPL", next_earnings_date: "2026-11-02", analyst_recommendation: "hold",
    analyst_counts: { strong_buy: 6, buy: 18, hold: 14, sell: 3, strong_sell: 3 },
    shareholder_meetings: [{ form: "DEF 14A", filing_date: "2026-01-08", accession_number: "x" }],
  })));
  render(<FluentProvider theme={webDarkTheme}><OverviewTab symbol="AAPL" q={q} /></FluentProvider>);
  expect(screen.getByText("Range change (6mo)")).toBeTruthy();
  expect(screen.getByText("-2.50%")).toBeTruthy();
  expect(screen.getByText("101.23")).toBeTruthy();
  expect(screen.getByText(/ORB unavailable/)).toBeTruthy();
  await waitFor(() => expect(screen.getByText("2026-11-02")).toBeTruthy());
  expect(screen.getByText("hold")).toBeTruthy();
  expect(screen.getByText(/Strong buy 6 · Buy 18 · Hold 14 · Sell 3 · Strong sell 3/)).toBeTruthy();
  expect(screen.getByText("DEF 14A · 2026-01-08")).toBeTruthy();
});
```

- [ ] **Step 2: Run to see them fail** — `npx vitest run src/lib/api.holders src/pages/stock/OverviewTab` — FAIL (no `clearHoldersMemo`; no module).

- [ ] **Step 3: Implement the API changes** exactly as listed in Interfaces. The memo:
```ts
const holdersMemo = new Map<string, { at: number; p: Promise<HoldersResult> }>();
const HOLDERS_TTL = 10 * 60_000;
export const clearHoldersMemo = () => holdersMemo.clear();
function holdersMemoised(symbol: string): Promise<HoldersResult> {
  const key = symbol.toUpperCase();
  const hit = holdersMemo.get(key);
  if (hit && Date.now() - hit.at < HOLDERS_TTL) return hit.p;
  const p = getJson<HoldersResult>(`/api/holders/${encodeURIComponent(key)}`);
  holdersMemo.set(key, { at: Date.now(), p });
  p.catch(() => { if (holdersMemo.get(key)?.p === p) holdersMemo.delete(key); });
  return p;
}
```
and set `holders: holdersMemoised` in the `api` object (replacing the old wrapper). Keep `Security` as-is; `SecurityDetail` extends it.

- [ ] **Step 4: Implement `OverviewTab.tsx`**

```tsx
import { Badge } from "@fluentui/react-components";
import type { ReactNode } from "react";
import { useApi } from "../../lib/useApi";
import { api, type SecurityDetail, type Studies } from "../../lib/api";
import { fmtInt, fmtNum, signed, tone } from "../../lib/fmt";
import Block from "../../blocks/Block";

const STUDY_ROWS: [keyof Studies, string][] = [
  ["sma20", "SMA 20"], ["sma50", "SMA 50"], ["ema12", "EMA 12"], ["ema26", "EMA 26"], ["rsi14", "RSI 14"],
  ["macd", "MACD"], ["macd_signal", "MACD signal"], ["macd_histogram", "MACD hist"],
  ["bollinger_upper", "Bollinger upper"], ["bollinger_mid", "Bollinger mid"], ["bollinger_lower", "Bollinger lower"],
];
const ORB_COLOR = { ABOVE_RANGE: "success", BELOW_RANGE: "danger", INSIDE_RANGE: "informative" } as const;

const Stat = ({ k, v }: { k: string; v: ReactNode }) => (
  <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", borderBottom: "1px solid var(--hair)" }}>
    <span style={{ color: "var(--dim)" }}>{k}</span><span className="num">{v}</span>
  </div>
);

export default function OverviewTab({ symbol, q }: { symbol: string; q: SecurityDetail | undefined }) {
  const ev = useApi(`events:${symbol}`, () => api.events(symbol));
  const e = ev.data;
  const studies = q ? STUDY_ROWS.filter(([k]) => k in (q.studies ?? {})) : [];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 12, alignItems: "start" }}>
      <Block fixed title="Quote">
        {q && (
          <>
            <Stat k="Previous close" v={fmtNum(q.previous_close)} />
            <Stat k="Day range" v={`${fmtNum(q.day_low)} – ${fmtNum(q.day_high)}`} />
            <Stat k="52-week range" v={`${fmtNum(q.week52_low)} – ${fmtNum(q.week52_high)}`} />
            <Stat k="Volume" v={fmtInt(q.volume)} />
            <Stat k={`Range change (${q.range})`} v={<span style={{ color: tone(q.range_change_pct) }}>{q.range_change_pct == null ? "—" : `${signed(q.range_change_pct)}%`}</span>} />
            <Stat k="Type" v={q.instrument_type ?? "—"} />
            <Stat k="Exchange" v={q.exchange ?? "—"} />
            <Stat k="Currency" v={q.currency ?? "—"} />
          </>
        )}
      </Block>
      <Block fixed title="Events" loading={ev.loading} error={ev.error} fetchedAt={ev.fetchedAt}>
        {e && (
          <>
            <Stat k="Next earnings" v={e.next_earnings_date ?? "unknown"} />
            <Stat k="Analysts" v={e.analyst_recommendation ?? "n/a"} />
            {e.analyst_counts && (
              <div style={{ color: "var(--dim)", padding: "4px 0" }}>
                Strong buy {e.analyst_counts.strong_buy} · Buy {e.analyst_counts.buy} · Hold {e.analyst_counts.hold} · Sell {e.analyst_counts.sell} · Strong sell {e.analyst_counts.strong_sell}
              </div>
            )}
            <div style={{ marginTop: 6, fontWeight: 600 }}>Shareholder meetings</div>
            {e.shareholder_meetings.length
              ? e.shareholder_meetings.slice(0, 5).map((m) => <div key={m.accession_number}>{`${m.form} · ${m.filing_date}`}</div>)
              : <div style={{ color: "var(--dim)" }}>None on file.</div>}
          </>
        )}
      </Block>
      <Block fixed title="Studies">
        {q && (
          <>
            {studies.length
              ? studies.map(([k, label]) => <Stat key={k} k={label} v={fmtNum(q.studies[k] ?? null)} />)
              : <div style={{ color: "var(--dim)" }}>Not enough history to compute studies at this range.</div>}
            <div style={{ marginTop: 8, fontWeight: 600 }}>Opening range breakout</div>
            {q.orb == null ? (
              <div style={{ color: "var(--dim)" }}>ORB unavailable (needs today's intraday bars — try during market hours).</div>
            ) : (
              <>
                <Badge appearance="tint" color={ORB_COLOR[q.orb.status]}>{q.orb.status.replace("_", " ")}</Badge>
                <Stat k="Range" v={`${fmtNum(q.orb.range_low)} – ${fmtNum(q.orb.range_high)}`} />
                <Stat k="Breakout" v={<span style={{ color: tone(q.orb.breakout_pct) }}>{q.orb.breakout_pct === 0 ? "—" : `${signed(q.orb.breakout_pct)}%`}</span>} />
              </>
            )}
          </>
        )}
      </Block>
    </div>
  );
}
```

In `StockPage.tsx`: import `OverviewTab`; replace the `tab === "overview" && q ? (<Card …>…</Card>)` branch with `tab === "overview" ? <OverviewTab symbol={symbol} q={q} />`; keep the `PlaceholderPage` fallback for the other tabs; remove now-unused imports (`Card`, `Num` only if unused — the header still uses `Num`).

- [ ] **Step 5: Run tests, typecheck, build** — `npx vitest run`, `npx tsc --noEmit`, `npm run build`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/api.holders.test.ts frontend/src/pages/stock frontend/src/pages/StockPage.tsx
git add -A src/howlet/static/app
git commit -m "Frontend: stock Overview with events, studies and ORB; memoised holders"
```

---

### Task 2: Chart tab (KLineChart)

**Files:**
- Modify: `frontend/package.json` (+ lockfile), `frontend/src/pages/StockPage.tsx`
- Create: `frontend/src/lib/chart.ts`, `frontend/src/components/KlineChart.tsx`, `frontend/src/pages/stock/ChartTab.tsx`
- Test: `frontend/src/lib/chart.test.ts`

**Interfaces:**
- Consumes: `api.security(symbol, range)`, `SecurityDetail` (Task 1); `useApi`; `useSettings` (`chartRange`, `indicators`, `update`); `Block`.
- Produces:
  - `chart.ts`: `CHART_RANGES = ["1d","5d","1mo","3mo","6mo","1y","5y","max"] as const`; `MAIN_PANE = ["MA","EMA","BOLL","SAR","BBI"]`; `INDICATORS: { name: string; label: string; main: boolean }[]` — on price: MA, EMA, BOLL "Bollinger", SAR, BBI; own pane: VOL "Volume", MACD, RSI, KDJ, OBV, CCI, WR "Williams %R", TRIX, ROC, DMI, MTM "Momentum", PSY; `DRAW_TOOLS: [string, string][]` = `segment` "Line", `rayLine` "Ray", `horizontalStraightLine` "H-line", `priceLine` "Price", `priceChannelLine` "Channel", `fibonacciLine` "Fib", `simpleAnnotation` "Note"; `barsFromSecurity(s: SecurityDetail): { timestamp: number; open: number; high: number; low: number; close: number; volume: number }[]` (timestamps are epoch **seconds** → ms; length = `history_ts.length`); `chartStyles(v: (name: string) => string): object` — the mapping from inventory §2b using token names `--hair`, `--up`, `--down`, `--text`, `--dim`, `--border`, `--accent`, `--bg`, `--cyan`.
  - `KlineChart({ bars, indicators, onIndicatorsChange?, drawTool })` — default export, imported with `React.lazy` from `ChartTab`. `init` on mount into a 460 px-high div, `setStyles(chartStyles(readVar))` with `readVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim()`, `applyNewData(bars)` whenever `bars` changes, keeps indicators in sync with the `indicators` prop (create missing via `createIndicator(name, MAIN_PANE.includes(name), MAIN_PANE.includes(name) ? { id: "candle_pane" } : undefined)`, remember the returned pane id; remove dropped via `removeIndicator(paneId, name)`), calls `createOverlay(drawTool.name)` each time `drawTool.nonce` changes (`drawTool: { name: string; nonce: number } | null`; name `"__clear__"` → `removeOverlay()`), resizes with a `ResizeObserver` (guarded), re-applies styles when the theme changes (subscribe to `useSettings` `themeMode`/`accent` and `matchMedia('(prefers-color-scheme: dark)')`), and `dispose(el)` on unmount.
  - `ChartTab({ symbol })` — range buttons (`CHART_RANGES`, active = state initialised from `settings.chartRange`), fetches `api.security(symbol, range)` with key `chart:${symbol}:${range}` (no auto-refresh); a Fluent `Dropdown` "+ Indicator" listing `INDICATORS` not already active (grouped "On price" / "Own pane"); active indicators as dismissible `Tag`s; draw-tool buttons + "Clear drawings". Active indicators are `settings.indicators` and every add/remove calls `update({ indicators })` so they persist. The chart sits in a `Block fixed` titled `${symbol} · ${range}`; while the chunk loads show "Loading chart…" via `<Suspense>`.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/chart.test.ts`:
```ts
import { barsFromSecurity, chartStyles, CHART_RANGES, INDICATORS, MAIN_PANE } from "./chart";
import type { SecurityDetail } from "./api";

test("bars convert seconds to ms and keep OHLCV aligned", () => {
  const s = { history_ts: [1, 2], history_open: [10, 11], history_high: [12, 13], history_low: [9, 10],
    history_close: [11, 12], history_volume: [100, 200] } as unknown as SecurityDetail;
  expect(barsFromSecurity(s)).toEqual([
    { timestamp: 1000, open: 10, high: 12, low: 9, close: 11, volume: 100 },
    { timestamp: 2000, open: 11, high: 13, low: 10, close: 12, volume: 200 },
  ]);
});

test("styles come from the CSS variables, not literals", () => {
  const vars: Record<string, string> = { "--up": "U", "--down": "D", "--hair": "H", "--text": "T", "--dim": "M",
    "--border": "B", "--accent": "A", "--bg": "G", "--cyan": "C" };
  const st = chartStyles((n) => vars[n]) as any;
  expect(st.candle.bar.upColor).toBe("U");
  expect(st.candle.bar.downWickColor).toBe("D");
  expect(st.grid.horizontal.color).toBe("H");
  expect(st.crosshair.horizontal.text.backgroundColor).toBe("A");
  expect(st.overlay.line.color).toBe("C");
  expect(JSON.stringify(st)).not.toMatch(/#[0-9a-f]{3,6}/i);
});

test("catalogue sanity", () => {
  expect(CHART_RANGES).toContain("6mo");
  expect(INDICATORS.filter((i) => i.main).map((i) => i.name)).toEqual(MAIN_PANE);
  expect(INDICATORS.find((i) => i.name === "WR")?.label).toBe("Williams %R");
});
```

- [ ] **Step 2: Run to see it fail** — `npx vitest run src/lib/chart` — FAIL.

- [ ] **Step 3: Add the dependency** — `npm install --save-exact klinecharts@9.8.12`; confirm `package.json` shows `"klinecharts": "9.8.12"`.

- [ ] **Step 4: Implement `chart.ts`**

```ts
import type { SecurityDetail } from "./api";

export const CHART_RANGES = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "5y", "max"] as const;
export const MAIN_PANE = ["MA", "EMA", "BOLL", "SAR", "BBI"];
export const INDICATORS: { name: string; label: string; main: boolean }[] = [
  ...[["MA", "MA"], ["EMA", "EMA"], ["BOLL", "Bollinger"], ["SAR", "SAR"], ["BBI", "BBI"]].map(([name, label]) => ({ name, label, main: true })),
  ...[["VOL", "Volume"], ["MACD", "MACD"], ["RSI", "RSI"], ["KDJ", "KDJ"], ["OBV", "OBV"], ["CCI", "CCI"], ["WR", "Williams %R"],
    ["TRIX", "TRIX"], ["ROC", "ROC"], ["DMI", "DMI"], ["MTM", "Momentum"], ["PSY", "PSY"]].map(([name, label]) => ({ name, label, main: false })),
];
export const DRAW_TOOLS: [string, string][] = [
  ["segment", "Line"], ["rayLine", "Ray"], ["horizontalStraightLine", "H-line"], ["priceLine", "Price"],
  ["priceChannelLine", "Channel"], ["fibonacciLine", "Fib"], ["simpleAnnotation", "Note"],
];

export type Bar = { timestamp: number; open: number; high: number; low: number; close: number; volume: number };

export const barsFromSecurity = (s: SecurityDetail): Bar[] =>
  s.history_ts.map((t, i) => ({
    timestamp: t * 1000, open: s.history_open[i], high: s.history_high[i], low: s.history_low[i],
    close: s.history_close[i], volume: s.history_volume[i],
  }));

// Inventory §2b mapping; every colour is read from a CSS variable at call time.
export function chartStyles(v: (name: string) => string): object {
  const up = v("--up"), down = v("--down"), dim = v("--dim");
  return {
    grid: { horizontal: { color: v("--hair") }, vertical: { color: v("--hair") } },
    candle: {
      bar: { upColor: up, downColor: down, upBorderColor: up, downBorderColor: down, upWickColor: up, downWickColor: down },
      priceMark: { last: { upColor: up, downColor: down } },
      tooltip: { text: { color: v("--text") } },
    },
    indicator: { tooltip: { text: { color: dim } } },
    xAxis: { tickText: { color: dim } },
    yAxis: { tickText: { color: dim } },
    separator: { color: v("--border") },
    crosshair: {
      horizontal: { line: { color: dim }, text: { backgroundColor: v("--accent"), color: v("--bg") } },
      vertical: { line: { color: dim }, text: { backgroundColor: v("--accent"), color: v("--bg") } },
    },
    overlay: {
      point: { color: v("--accent"), borderColor: v("--border") },
      line: { color: v("--cyan") },
      text: { color: v("--bg"), backgroundColor: v("--accent") },
    },
  };
}
```

- [ ] **Step 5: Implement `KlineChart.tsx`**

```tsx
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
```
If a `klinecharts` type name differs in 9.8.12 (e.g. `DeepPartial`), import what the package actually exports (`grep -n "export" node_modules/klinecharts/dist/index.d.ts | head -80`) and note it; behaviour must stay the same.

- [ ] **Step 6: Implement `ChartTab.tsx`**

```tsx
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
```
In `StockPage.tsx` render `<ChartTab symbol={symbol} />` when `tab === "chart"`.

- [ ] **Step 7: Run tests, typecheck, build** — `npx vitest run`, `npx tsc --noEmit`, `npm run build`. Expect a separate `KlineChart-*.js` chunk in the build output; record both chunk sizes in the report.

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/chart.ts frontend/src/lib/chart.test.ts frontend/src/components/KlineChart.tsx frontend/src/pages/stock/ChartTab.tsx frontend/src/pages/StockPage.tsx
git add -A src/howlet/static/app
git commit -m "Frontend: Chart tab with KLineChart 9.8.12 (ranges, indicators, drawing)"
```

---

### Task 3: Financials and News tabs

**Files:**
- Create: `frontend/src/pages/stock/FinancialsTab.tsx`, `frontend/src/pages/stock/NewsTab.tsx`
- Modify: `frontend/src/pages/StockPage.tsx`
- Test: `frontend/src/pages/stock/FinancialsTab.test.tsx`

**Interfaces:**
- Consumes: `api.facts`, `api.newsFor`, `Facts`, `FiscalYear` (Task 1); `useApi`; `Block`; `DataTable`, `tableCsv`; `downloadCsv`; `NewsList`; `fmtMoney`, `fmtNum`, `tone`.
- Produces:
  - `FinancialsTab({ symbol })` — `Block fixed sec` titled `Annual financials · ${company}` (from data, else "Annual financials"), `DataTable` of `fiscal_years` (server order): Fiscal year (`FY${fiscal_year}` + dim `end_date`), Revenue, Net income (toned), EPS (diluted) (2dp, "—" for null), Total assets, Total liabilities, Equity, Operating cash flow (all `fmtMoney`). `actions`: **Export CSV** → `downloadCsv(\`${symbol}-financials.csv\`, tableCsv(...))`. Empty → "No annual XBRL facts (fund, foreign issuer, or non-10-K filer)." No auto-refresh.
  - `NewsTab({ symbol })` — `api.newsFor([symbol], 15)`, refresh 300 000 ms, `Block fixed` titled `News · ${symbol}`, `NewsList` empty "No headlines for this symbol.".

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/stock/FinancialsTab.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import FinancialsTab from "./FinancialsTab";

afterEach(() => vi.restoreAllMocks());
const wrap = (ui: JSX.Element) => render(<FluentProvider theme={webDarkTheme}>{ui}</FluentProvider>);

test("renders fiscal years with money formatting and raw end dates", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ symbol: "AAPL", cik: "1", company: "Apple Inc.",
    fiscal_years: [{ fiscal_year: 2025, end_date: "2025-09-27", revenue: 416161000000, net_income: -1e9, eps_diluted: 7.46,
      total_assets: 359241000000, total_liabilities: null, stockholders_equity: 73733000000, operating_cash_flow: 111482000000 }] })));
  wrap(<FinancialsTab symbol="AAPL" />);
  await waitFor(() => expect(screen.getByText("FY2025")).toBeTruthy());
  expect(screen.getByText("2025-09-27")).toBeTruthy();
  expect(screen.getByText("$416.16B")).toBeTruthy();
  expect(screen.getByText("-$1.00B")).toBeTruthy();
  expect(screen.getByText("7.46")).toBeTruthy();
  expect(screen.getByText("Annual financials · Apple Inc.")).toBeTruthy();
});

test("SEC error text is shown", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: "No SEC filer for ZZZZ" }), { status: 404 }));
  wrap(<FinancialsTab symbol="ZZZZ" />);
  await waitFor(() => expect(screen.getByText("No SEC filer for ZZZZ")).toBeTruthy());
});
```

- [ ] **Step 2: Run to see it fail** — `npx vitest run src/pages/stock/FinancialsTab` — FAIL.

- [ ] **Step 3: Implement**

`frontend/src/pages/stock/FinancialsTab.tsx`:
```tsx
import { Button } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type FiscalYear } from "../../lib/api";
import { fmtMoney, fmtNum, tone } from "../../lib/fmt";
import { downloadCsv } from "../../lib/csv";
import Block from "../../blocks/Block";
import DataTable, { tableCsv, type Column } from "../../components/DataTable";

const money = (k: keyof FiscalYear, label: string, toned = false): Column<FiscalYear> => ({
  key: k, label, align: "right",
  render: (r) => <span className="num" style={toned ? { color: tone(r[k] as number | null) } : undefined}>{fmtMoney(r[k] as number | null)}</span>,
  csv: (r) => r[k] as number | null,
});

const COLS: Column<FiscalYear>[] = [
  { key: "fy", label: "Fiscal year", render: (r) => <><b>{`FY${r.fiscal_year}`}</b> <span style={{ color: "var(--dim)" }}>{r.end_date}</span></>, csv: (r) => r.fiscal_year },
  money("revenue", "Revenue"),
  money("net_income", "Net income", true),
  { key: "eps", label: "EPS (diluted)", align: "right", render: (r) => <span className="num">{fmtNum(r.eps_diluted)}</span>, csv: (r) => r.eps_diluted },
  money("total_assets", "Total assets"),
  money("total_liabilities", "Total liabilities"),
  money("stockholders_equity", "Equity"),
  money("operating_cash_flow", "Operating cash flow"),
];

export default function FinancialsTab({ symbol }: { symbol: string }) {
  const { data, error, loading, fetchedAt } = useApi(`facts:${symbol}`, () => api.facts(symbol));
  return (
    <Block fixed sec title={data ? `Annual financials · ${data.company}` : "Annual financials"} loading={loading} error={error} fetchedAt={fetchedAt}
      actions={data?.fiscal_years.length ? <Button size="small" onClick={() => downloadCsv(`${symbol}-financials.csv`, tableCsv(COLS, data.fiscal_years))}>Export CSV</Button> : undefined}>
      {data && <DataTable columns={COLS} rows={data.fiscal_years} rowKey={(r) => String(r.fiscal_year)}
        empty="No annual XBRL facts (fund, foreign issuer, or non-10-K filer)." />}
    </Block>
  );
}
```

`frontend/src/pages/stock/NewsTab.tsx`:
```tsx
import { useApi } from "../../lib/useApi";
import { api } from "../../lib/api";
import Block from "../../blocks/Block";
import NewsList from "../../components/NewsList";

const FIVE_MIN = 300_000;

export default function NewsTab({ symbol }: { symbol: string }) {
  const { data, error, loading, fetchedAt } = useApi(`news:${symbol}`, () => api.newsFor([symbol], 15), FIVE_MIN);
  return (
    <Block fixed title={`News · ${symbol}`} loading={loading} error={error} fetchedAt={fetchedAt} refreshMs={FIVE_MIN}>
      {data && <NewsList items={data} empty="No headlines for this symbol." />}
    </Block>
  );
}
```
In `StockPage.tsx` route `financials` → `<FinancialsTab symbol={symbol} />`, `news` → `<NewsTab symbol={symbol} />`.

- [ ] **Step 4: Run tests, typecheck, build** — `npx vitest run`, `npx tsc --noEmit`, `npm run build`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/stock/FinancialsTab.tsx frontend/src/pages/stock/FinancialsTab.test.tsx frontend/src/pages/stock/NewsTab.tsx frontend/src/pages/StockPage.tsx
git add -A src/howlet/static/app
git commit -m "Frontend: stock Financials and News tabs"
```

---

### Task 4: Holders tab (13F holders, insiders, filings)

**Files:**
- Create: `frontend/src/pages/stock/HoldersTab.tsx`
- Modify: `frontend/src/pages/StockPage.tsx`
- Test: `frontend/src/pages/stock/HoldersTab.test.tsx`

**Interfaces:**
- Consumes: `api.holders` (memoised), `api.insiders`, `api.filings`, types `Holder`, `InsiderTxn`, `Filing` (Task 1); `useApi`; `Block`; `DataTable`; `fmtInt`, `fmtMoney`, `fmtNum`; `safeHref`.
- Produces: `HoldersTab({ symbol })` — three independent `Block fixed sec` panels:
  1. **Tracked superinvestors** (`api.holders`, key `holders:${symbol}` — the same promise the 🦉 chips use): columns Manager / Shares (`fmtInt`) / Value (`fmtMoney`) / Portfolio weight (`fmtNum(weight_pct, 1)%`) / As of (`period_of_report` raw); sorted by `value_usd` desc (server order). Empty: `None of the tracked managers (${tracked_managers.join(", ")}) reported holding ${symbol} in their latest 13F.` While loading with no data: "Checking every tracked manager's latest 13F (the first lookup can take a minute)…".
  2. **Insider transactions (Form 4)** (`api.insiders(symbol, 15)`, refresh 300 000): summary line `last ${filings_scanned} Form 4s · ${open_market_purchases} buys ${fmtMoney(purchase_value_usd)} · ${open_market_sales} sells ${fmtMoney(sale_value_usd)}`; table of the first 20 `transactions`: Date (raw, "?" if null) / Insider (with `title` = relationship) / Type (`code_label`, colour `var(--up)` for code "P", `var(--down)` for "S", else dim) / Shares (`fmtInt`) / Price (`fmtNum`, "—") / Value (`fmtMoney`). Empty: "No non-derivative insider transactions in these filings.".
  3. **SEC filings** (`api.filings(symbol, 15)`, refresh 300 000): rows Filed (raw) / Form (link via `safeHref(url)`, "?" if null) / Period (raw, "—"). Empty: "No recent SEC filings.".

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/stock/HoldersTab.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import HoldersTab from "./HoldersTab";
import { clearHoldersMemo } from "../../lib/api";

afterEach(() => { vi.restoreAllMocks(); clearHoldersMemo(); });
const json = (b: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(b), { status }));

test("three panels load independently; P/S colouring; empty holders text names managers", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const u = String(input);
    if (u.startsWith("/api/holders")) return json({ symbol: "ZZ", tracked_managers: ["buffett", "ackman"], holders: [] });
    if (u.startsWith("/api/insiders")) return json({ symbol: "ZZ", company: "Z", filings_scanned: 3,
      summary: { open_market_purchases: 1, purchase_value_usd: 5e6, open_market_sales: 0, sale_value_usd: 0 },
      transactions: [{ insider: "Jane Doe", relationship: "CEO", date: "2026-10-20", code: "P", code_label: "Open-market purchase",
        shares: 1000, price_per_share: 50, value_usd: 50000, filing_date: "2026-10-22", accession_number: "a1" }] });
    return json({ error: "EDGAR down" }, 502);
  });
  render(<FluentProvider theme={webDarkTheme}><HoldersTab symbol="ZZ" /></FluentProvider>);
  await waitFor(() => expect(screen.getByText(/None of the tracked managers \(buffett, ackman\) reported holding ZZ/)).toBeTruthy());
  expect(screen.getByText(/last 3 Form 4s · 1 buys \$5\.0M · 0 sells/)).toBeTruthy();
  const buy = screen.getByText("Open-market purchase");
  expect(buy.getAttribute("style")).toContain("var(--up)");
  expect(screen.getByText("2026-10-20")).toBeTruthy();
  await waitFor(() => expect(screen.getByText("EDGAR down")).toBeTruthy());
});
```

- [ ] **Step 2: Run to see it fail** — FAIL (module not found).

- [ ] **Step 3: Implement `HoldersTab.tsx`**

```tsx
import { Link } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type Filing, type Holder, type InsiderTxn } from "../../lib/api";
import { fmtInt, fmtMoney, fmtNum, safeHref } from "../../lib/fmt";
import Block from "../../blocks/Block";
import DataTable, { type Column } from "../../components/DataTable";

const FIVE_MIN = 300_000;
const num = (s: string) => <span className="num">{s}</span>;

const HOLDER_COLS: Column<Holder>[] = [
  { key: "m", label: "Manager", render: (r) => r.manager },
  { key: "s", label: "Shares", align: "right", render: (r) => num(fmtInt(r.shares)) },
  { key: "v", label: "Value", align: "right", render: (r) => num(fmtMoney(r.value_usd)) },
  { key: "w", label: "Portfolio weight", align: "right", render: (r) => num(`${fmtNum(r.weight_pct, 1)}%`) },
  { key: "p", label: "As of", render: (r) => r.period_of_report ?? "—" },
];

const codeColor = (c: string) => (c === "P" ? "var(--up)" : c === "S" ? "var(--down)" : "var(--dim)");
const TXN_COLS: Column<InsiderTxn>[] = [
  { key: "d", label: "Date", render: (r) => r.date ?? "?" },
  { key: "i", label: "Insider", render: (r) => <span title={r.relationship ?? undefined}>{r.insider}</span> },
  { key: "t", label: "Type", render: (r) => <span style={{ color: codeColor(r.code) }}>{r.code_label}</span> },
  { key: "s", label: "Shares", align: "right", render: (r) => num(fmtInt(r.shares)) },
  { key: "p", label: "Price", align: "right", render: (r) => num(fmtNum(r.price_per_share)) },
  { key: "v", label: "Value", align: "right", render: (r) => num(fmtMoney(r.value_usd)) },
];

const FILING_COLS: Column<Filing>[] = [
  { key: "d", label: "Filed", render: (r) => r.filing_date },
  { key: "f", label: "Form", render: (r) => <Link href={safeHref(r.url)} target="_blank" rel="noopener noreferrer">{r.form ?? "?"}</Link> },
  { key: "p", label: "Period", render: (r) => r.period_of_report ?? "—" },
];

export default function HoldersTab({ symbol }: { symbol: string }) {
  const h = useApi(`holders:${symbol}`, () => api.holders(symbol));
  const ins = useApi(`insiders:${symbol}`, () => api.insiders(symbol, 15), FIVE_MIN);
  const fil = useApi(`filings:${symbol}`, () => api.filings(symbol, 15), FIVE_MIN);
  const s = ins.data?.summary;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: 12, alignItems: "start" }}>
      <Block fixed sec title="Tracked superinvestors (13F)" loading={h.loading} error={h.error} fetchedAt={h.fetchedAt}>
        {!h.data && !h.error && <span style={{ color: "var(--dim)" }}>Checking every tracked manager's latest 13F (the first lookup can take a minute)…</span>}
        {h.data && <DataTable columns={HOLDER_COLS} rows={h.data.holders} rowKey={(r) => r.manager + r.issuer}
          empty={`None of the tracked managers (${h.data.tracked_managers.join(", ")}) reported holding ${symbol} in their latest 13F.`} />}
      </Block>
      <Block fixed sec title="Insider transactions (Form 4)" loading={ins.loading} error={ins.error} fetchedAt={ins.fetchedAt} refreshMs={FIVE_MIN}>
        {ins.data && s && (
          <>
            <div style={{ color: "var(--dim)", marginBottom: 6 }}>
              {`last ${ins.data.filings_scanned} Form 4s · ${s.open_market_purchases} buys ${fmtMoney(s.purchase_value_usd)} · ${s.open_market_sales} sells ${fmtMoney(s.sale_value_usd)}`}
            </div>
            <DataTable columns={TXN_COLS} rows={ins.data.transactions.slice(0, 20)} rowKey={(r) => `${r.accession_number}-${r.insider}-${r.date}-${r.shares}`}
              empty="No non-derivative insider transactions in these filings." />
          </>
        )}
      </Block>
      <Block fixed sec title="SEC filings" loading={fil.loading} error={fil.error} fetchedAt={fil.fetchedAt} refreshMs={FIVE_MIN}>
        {fil.data && <DataTable columns={FILING_COLS} rows={fil.data.filings} rowKey={(r) => r.accession_number} empty="No recent SEC filings." />}
      </Block>
    </div>
  );
}
```
In `StockPage.tsx` route `holders` → `<HoldersTab symbol={symbol} />`.

- [ ] **Step 4: Run tests, typecheck, build.**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/stock/HoldersTab.tsx frontend/src/pages/stock/HoldersTab.test.tsx frontend/src/pages/StockPage.tsx
git add -A src/howlet/static/app
git commit -m "Frontend: stock Holders tab (13F holders, Form 4 insiders, SEC filings)"
```

---

### Task 5: Options tab

**Files:**
- Create: `frontend/src/pages/stock/OptionsTab.tsx`
- Modify: `frontend/src/pages/StockPage.tsx`
- Test: `frontend/src/pages/stock/OptionsTab.test.tsx`

**Interfaces:**
- Consumes: `api.options(symbol, expiration?)`, `OptionContract`, `OptionsChain` (Task 1); `useApi`; `Block`; `DataTable`; `fmtNum`, `fmtInt`.
- Produces: `OptionsTab({ symbol })` — state `expiration: string | undefined` (undefined = server default); fetch key `options:${symbol}:${expiration ?? ""}`; header row: "Underlying {fmtNum(underlying_price)}" and a Fluent `Dropdown` of `expiration_dates` with `selected_expiration` selected (changing it sets state); a note "Experimental — unofficial Yahoo data, may go dark." Two `Block fixed` panels side by side (`repeat(auto-fit, minmax(420px, 1fr))`): **Calls** and **Puts**, columns Strike (`fmtNum`; `in_the_money` → `font-weight: 600` and `var(--up)` colour) / Last / Bid / Ask (`fmtNum`, "—") / Volume / Open int. (`fmtInt`) / IV (`implied_volatility` × 100, 1dp, "%", "—" if null). Empty side: "No contracts.". Errors (incl. 404 "No options data for …") degrade via `Block` (non-SEC).

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/stock/OptionsTab.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import OptionsTab from "./OptionsTab";

afterEach(() => vi.restoreAllMocks());

test("calls/puts render with IV as a percentage and ITM strikes emphasised", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    symbol: "AAPL", underlying_price: 347.73, expiration_dates: ["2026-10-26", "2026-11-02"], selected_expiration: "2026-10-26",
    calls: [{ contract_symbol: "C1", strike: 260, last_price: 87.15, bid: 85.8, ask: 89.45, volume: 3, open_interest: 4, implied_volatility: 2.1446, in_the_money: true }],
    puts: [],
  })));
  render(<FluentProvider theme={webDarkTheme}><OptionsTab symbol="AAPL" /></FluentProvider>);
  await waitFor(() => expect(screen.getByText("214.5%")).toBeTruthy());
  expect(screen.getByText("260.00").getAttribute("style")).toContain("var(--up)");
  expect(screen.getByText("No contracts.")).toBeTruthy();
  expect(screen.getByText(/Underlying/)).toBeTruthy();
});
```

- [ ] **Step 2: Run to see it fail.**

- [ ] **Step 3: Implement `OptionsTab.tsx`**

```tsx
import { Dropdown, Option } from "@fluentui/react-components";
import { useState } from "react";
import { useApi } from "../../lib/useApi";
import { api, type OptionContract } from "../../lib/api";
import { fmtInt, fmtNum } from "../../lib/fmt";
import Block from "../../blocks/Block";
import DataTable, { type Column } from "../../components/DataTable";

const n = (s: string) => <span className="num">{s}</span>;
const COLS: Column<OptionContract>[] = [
  { key: "k", label: "Strike", align: "right", render: (r) => <span className="num" style={r.in_the_money ? { fontWeight: 600, color: "var(--up)" } : undefined}>{fmtNum(r.strike)}</span> },
  { key: "l", label: "Last", align: "right", render: (r) => n(fmtNum(r.last_price)) },
  { key: "b", label: "Bid", align: "right", render: (r) => n(fmtNum(r.bid)) },
  { key: "a", label: "Ask", align: "right", render: (r) => n(fmtNum(r.ask)) },
  { key: "v", label: "Volume", align: "right", render: (r) => n(fmtInt(r.volume)) },
  { key: "o", label: "Open int.", align: "right", render: (r) => n(fmtInt(r.open_interest)) },
  { key: "iv", label: "IV", align: "right", render: (r) => n(r.implied_volatility == null ? "—" : `${fmtNum(r.implied_volatility * 100, 1)}%`) },
];

export default function OptionsTab({ symbol }: { symbol: string }) {
  const [expiration, setExpiration] = useState<string | undefined>();
  const { data, error, loading, fetchedAt } = useApi(`options:${symbol}:${expiration ?? ""}`, () => api.options(symbol, expiration));
  const sel = data?.selected_expiration ?? expiration ?? "";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        {data && <span>Underlying <span className="num">{fmtNum(data.underlying_price)}</span></span>}
        {data && data.expiration_dates.length > 0 && (
          <Dropdown size="small" value={sel} selectedOptions={[sel]} onOptionSelect={(_, d) => setExpiration(d.optionValue)} aria-label="Expiration">
            {data.expiration_dates.map((d) => <Option key={d} value={d}>{d}</Option>)}
          </Dropdown>
        )}
        <span style={{ color: "var(--dim)" }}>Experimental — unofficial Yahoo data, may go dark.</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: 12, alignItems: "start" }}>
        <Block fixed title="Calls" loading={loading} error={error} fetchedAt={fetchedAt}>
          {data && <DataTable columns={COLS} rows={data.calls} rowKey={(r) => r.contract_symbol} empty="No contracts." />}
        </Block>
        <Block fixed title="Puts" loading={loading} error={error} fetchedAt={fetchedAt}>
          {data && <DataTable columns={COLS} rows={data.puts} rowKey={(r) => r.contract_symbol} empty="No contracts." />}
        </Block>
      </div>
    </div>
  );
}
```
In `StockPage.tsx` route `options` → `<OptionsTab symbol={symbol} />` (the tab is still hidden unless Settings → Show Options is on, but a direct `#/stock/AAPL/options` link works).

- [ ] **Step 4: Run tests, typecheck, build.**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/stock/OptionsTab.tsx frontend/src/pages/stock/OptionsTab.test.tsx frontend/src/pages/StockPage.tsx
git add -A src/howlet/static/app
git commit -m "Frontend: stock Options tab (experimental)"
```

---

### Task 6: Page map, cleanup, docs and live pass

**Files:**
- Modify: `frontend/src/App.tsx`, `frontend/src/pages/StockPage.tsx`, `CLAUDE.md`
- Test: existing suites

**Interfaces:**
- Produces: no new exports.

- [ ] **Step 1: `App.tsx` page map.** Replace the nested page ternary with a lookup: 
```tsx
const PAGES: Partial<Record<PageId, () => JSX.Element>> = {
  home: () => <HomePage />, markets: () => <MarketsPage />, news: () => <NewsPage />,
  screener: () => <ScreenerPage />, settings: () => <SettingsPage />,
};
// ...
const page = route.kind === "stock"
  ? <StockPage symbol={route.symbol} tab={route.tab} />
  : (PAGES[route.page]?.() ?? <PlaceholderPage title={PAGE_META[route.page].label} />);
```
(`PageId` from `lib/settings`; keep every page that is routed today.)

- [ ] **Step 2: `StockPage.tsx`.** It must now have no `PlaceholderPage` usage: every tab maps to its component. Remove the `PlaceholderPage` import. Verify with `grep -n PlaceholderPage frontend/src/pages/StockPage.tsx` → no output.

- [ ] **Step 3: CLAUDE.md** — extend the React status line under "## Status" with "stock page tabs: overview/events/studies/ORB, KLineChart chart, financials, holders/insiders/filings, news, options (2026-10-24)". In the Gotchas, update the KLineChart bullet's first sentence to say it is vendored for `/classic` and installed from npm (pinned 9.8.12) for the React app; keep the rest of that bullet.

- [ ] **Step 4: Run everything** — `npx vitest run`, `npx tsc --noEmit`, `npm run build`; from repo root `PYTHONPATH=src pytest tests/ -q` and `ruff check src/ tests/`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/pages/StockPage.tsx CLAUDE.md
git add -A src/howlet/static/app
git commit -m "Frontend: page lookup map; stock page fully ported; docs"
```

- [ ] **Step 6: Live pass (controller)** at `http://localhost:8813/#/stock/AAPL/overview`:
  1. Overview: quote stats incl. range change; events (next earnings 2026-11-02-style raw date, analyst counts, DEF 14A rows); studies; ORB (unavailable outside market hours).
  2. Chart: candles render in the theme colours; range buttons reload; adding RSI creates a pane, removing it removes the pane; indicators persist after reload; Line tool lets you draw; Clear drawings works; switching Windows light/dark re-themes the chart; the chart chunk loads only when the tab opens (Network panel).
  3. Financials: 5 fiscal years, CSV export. News: per-symbol headlines.
  4. Holders: chips and Holders tab issue only one `/api/holders/AAPL` request between them; insiders with P/S colours; filings links open sec.gov.
  5. Options (enable in Settings): expiry dropdown changes the chain.
  6. Console clean.
