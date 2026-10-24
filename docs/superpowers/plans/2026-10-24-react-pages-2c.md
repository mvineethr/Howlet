# Howlet React pages 2c: Smart Money and Portfolio — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the classic PORT, consensus, insider-buy screen, position history, N-PORT fund holdings, MY and PF screens — plus the never-surfaced EDGAR full-text search — into two rail pages: **Smart Money** (Managers · Consensus · Insider buys · Position history · Filing search · Funds) and **Portfolio** (Watchlists · Holdings & risk).

**Architecture:** Part 3 of 4 of the redesign's plan 2 (2a: News/Markets/Screener, 2b: stock page — both shipped). Classic reference: `docs/superpowers/plans/classic-inventory.md` §1 (PORT), §4 (MY), §5 (PF), widgets 3/8/9/17, §13 route table. Page routes gain optional path params (`#/smart/managers/buffett`) so sub-tabs and the selected manager survive Back and reload. The command box stops sending managers to `/classic`. No Python changes.

**Tech Stack:** React 18, TypeScript, Vite 5, Fluent UI v9, zustand, Vitest.

## Global Constraints

- No change to `views.py`, the MCP server, the CLI, any `/api/*` route, or `src/howlet/dashboard.html`.
- Colour hex literals only in `frontend/src/theme/tokens.ts`; numbers use `.num`; up/down via `tone()` / `var(--up|--down|--dim)`.
- Date-only strings (`period_of_report`, `filing_date`, `file_date`, `report_period_date`, Form 4 `date`) shown raw, never via `new Date`.
- External links only via `safeHref`, `target="_blank" rel="noopener noreferrer"`.
- SEC-backed panels (portfolio, diff, consensus, insider buys, position history, full-text, fund) use `Block sec`; market/news panels degrade quietly. Panels load independently.
- Shared classic keys keep their exact shapes: `howlet_watchlists_v1` = `{ [name]: string[] }`, `howlet_pf_holdings` = `[{ symbol, shares }]`. The React app may now **write** them (the classic page reads the same shapes), but never in a different shape. New state only in new keys (`howlet_smart_tab_v1`, `howlet_portfolio_tab_v1`).
- SEC is throttled server-side (~10 req/s) and EDGAR access is serialised: no SEC panel polls faster than the classic page did (none of these poll at all, except quotes/news).
- Run frontend commands from `frontend/`; build with `npm run build` and commit `src/howlet/static/app` (stage with `git add -A src/howlet/static/app`) in every task that changes UI. Verify live at `http://localhost:8813/`.

## File structure

```
frontend/src/
  lib/route.ts                 # page routes gain optional params
  lib/api.ts                   # + postJson; portfolio, consensus, insiderBuys, positionHistory, fulltext, fund, risk
  lib/watchlists.ts            # pure watchlist mutations + save (shape-compatible with classic)
  lib/holdings.ts              # pure PF holdings mutations + load/save
  shell/CommandBox.tsx         # managers route to Smart Money
  components/ManagerPicker.tsx # combobox: presets + typed CIK
  pages/SmartMoneyPage.tsx     # sub-tab shell
  pages/smart/ManagersTab.tsx, ConsensusTab.tsx, InsiderBuysTab.tsx, PositionHistoryTab.tsx, FilingSearchTab.tsx, FundsTab.tsx
  pages/PortfolioPage.tsx      # sub-tab shell + account switcher
  pages/portfolio/WatchlistsTab.tsx, HoldingsTab.tsx
  blocks/WatchlistBlock.tsx    # empty-list hint points at Portfolio
  App.tsx                      # PAGES gains smart + portfolio
```

---

### Task 1: Route params, API additions, Smart Money shell with Consensus

**Files:**
- Modify: `frontend/src/lib/route.ts`, `frontend/src/lib/route.test.ts`, `frontend/src/lib/api.ts`, `frontend/src/shell/CommandBox.tsx`, `frontend/src/App.tsx`
- Create: `frontend/src/pages/SmartMoneyPage.tsx`, `frontend/src/pages/smart/ConsensusTab.tsx`
- Test: `frontend/src/lib/route.test.ts` (extend), `frontend/src/pages/smart/ConsensusTab.test.tsx`

**Interfaces:**
- Consumes: `getJson`, `ApiError`, `NewsItem` (`api.ts`); `useApi`; `useRoute`; `Block`; `DataTable`, `tableCsv`; `downloadCsv`; `fmtMoney`, `fmtNum`; `readJson`, `writeJson`.
- Produces:
  - `route.ts`: `Route` page variant becomes `{ kind: "page"; page: PageId; params?: string[] }`. `parseHash` puts any path segments after a valid page into `params` (omitting the key entirely when there are none, so existing `toEqual` tests still pass); junk pages fall back without params. `formatRoute` appends `/` + each param `encodeURIComponent`-ed.
  - `api.ts` — new helper and wrappers (field names verified live 2026-10-24):
```ts
export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  let data: unknown = null;
  try { data = await res.json(); } catch { /* non-JSON body */ }
  if (!res.ok) {
    const msg = data && typeof data === "object" && "error" in data ? String((data as { error: unknown }).error) : `HTTP ${res.status}`;
    throw new ApiError(msg, res.status);
  }
  return data as T;
}
export type PortfolioPosition = { issuer: string; cusip: string; value_usd: number; shares: number; share_type: string;
  weight_pct: number; ticker: string | null; price: number | null; change_pct: number | null; currency: string | null; sparkline: number[] };
export type Portfolio = { identifier: string; cik: string; period_of_report: string | null; filing_date: string | null;
  accession_number: string; total_value_usd: number; position_count: number; positions: PortfolioPosition[] };
export type ConsensusRow = { issuer: string; cusip: string; manager_count: number; total_value_usd: number;
  combined_weight_pct: number; weights_pct: Record<string, number> };
export type Consensus = { managers: { label: string; period_of_report: string | null }[]; rows: ConsensusRow[] };
export type InsiderBuy = { symbol: string; insider: string; relationship: string | null; date: string | null; shares: number | null;
  price_per_share: number | null; value_usd: number | null; shares_owned_after: number | null; filing_date: string; accession_number: string };
export type InsiderBuys = { symbols_scanned: string[]; filings_per_symbol: number;
  summary: { symbol: string; buy_count: number; total_shares: number; total_value_usd: number; latest_date: string | null }[];
  buys: InsiderBuy[] };
export type PositionQuarter = { period_of_report: string | null; filing_date: string | null; shares: number; value_usd: number; weight_pct: number; held: boolean };
export type PositionHistory = { identifier: string; cik: string; query: string; issuer: string; cusips: string[]; quarters: PositionQuarter[] };
export type FullTextHit = { accession_number: string; cik: string; company: string; file_date: string; file_description: string | null;
  file_type: string | null; form: string; root_form?: string; url: string };
export type FullText = { query: string; forms: string[]; results: FullTextHit[] };
export type FundHolding = { name: string; title: string | null; cusip: string | null; balance: number | null; value_usd: number | null;
  pct_val: number | null; asset_cat: string | null; issuer_cat: string | null; country: string | null };
export type Fund = { symbol: string; registrant?: string | null; fund: string; series_id?: string; report_period_date: string | null;
  total_assets: number | null; net_assets: number | null; accession_number: string; position_count: number; holdings: FundHolding[] };
export type RiskPosition = { symbol: string; weight_pct: number; return_pct: number; annualized_volatility_pct: number; max_drawdown_pct: number };
export type Risk = { portfolio_return_pct?: number; portfolio_annualized_volatility_pct?: number; portfolio_max_drawdown_pct?: number;
  sharpe_ratio?: number | null; positions: RiskPosition[]; error?: string };
```
  and in the `api` object:
```ts
  portfolio: (id: string, top = 25) => getJson<Portfolio>(`/api/portfolio/${q(id)}?top=${top}`),
  consensus: (min = 2, limit = 25) => getJson<Consensus>(`/api/consensus?min=${min}&limit=${limit}`),
  insiderBuys: (symbols: string[], filings = 8) => getJson<InsiderBuys>(`/api/insider-buys?filings=${filings}&symbols=${q(symbols.join(","))}`),
  positionHistory: (id: string, query: string, quarters = 8) => getJson<PositionHistory>(`/api/position-history/${q(id)}/${q(query)}?quarters=${quarters}`),
  fulltext: (query: string, forms: string[] = [], limit = 25) =>
    getJson<FullText>(`/api/fulltext?q=${q(query)}&limit=${limit}${forms.length ? `&forms=${q(forms.join(","))}` : ""}`),
  fund: (symbol: string, top = 50) => getJson<Fund>(`/api/fund/${q(symbol)}?top=${top}`),
  risk: (holdings: { symbol: string; shares: number }[], range = "1y") => postJson<Risk>("/api/risk", { holdings, range }),
```
  - `CommandBox.tsx`: a `manager` command now does `go({ kind: "page", page: "smart", params: ["managers", cmd.id] })` instead of navigating to `/classic`.
  - `SmartMoneyPage({ params })` — `type SmartTab = "managers" | "consensus" | "insiders" | "history" | "search" | "funds"`; labels "Managers", "Consensus", "Insider buys", "Position history", "Filing search", "Funds". Active tab = `params[0]` when valid, else the last tab saved in `howlet_smart_tab_v1`, else `"managers"`. Selecting a tab calls `go({ kind: "page", page: "smart", params: [tab] })` and saves it. Renders `ConsensusTab` for consensus; every other tab renders `PlaceholderPage` until its task. Export `SMART_TABS` and `resolveSmartTab(params: string[] | undefined, saved: string | null): SmartTab` (pure).
  - `ConsensusTab()` — a min-managers `Dropdown` (2, 3, 4, 5; default 2); `api.consensus(min, 25)` keyed `consensus:${min}`; `Block fixed sec` titled `Consensus across ${managers.length} managers`, sub-caption the manager labels joined " / "; columns Issuer, Held by (`${manager_count} of ${managers.length}`, `var(--up)` colour), Managers (`Object.keys(weights_pct).join(", ")`, `title` = each `label: x.x%`), Combined weight (`fmtNum(combined_weight_pct, 1)%`), Total value (`fmtMoney`). CSV export `consensus.csv`. Empty "No overlapping positions found.". Loading hint "Comparing every tracked manager's latest 13F (first run maps tickers; can take a minute)…".
  - `App.tsx` `PAGES` gains `smart: () => <SmartMoneyPage params={route.kind === "page" ? route.params ?? [] : []} />` — pass the current route's params (read `route` inside the component instead if the PAGES map has no access to it; keep the map shape).

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/lib/route.test.ts`:
```ts
test("page params round-trip and are omitted when absent", () => {
  expect(parseHash("#/smart/managers/buffett", "home")).toEqual({ kind: "page", page: "smart", params: ["managers", "buffett"] });
  expect(parseHash("#/smart", "home")).toEqual({ kind: "page", page: "smart" });
  expect(parseHash("#/nope/x", "home")).toEqual({ kind: "page", page: "home" });
  const r = { kind: "page", page: "smart", params: ["history", "BRK B"] } as const;
  expect(formatRoute(r)).toBe("#/smart/history/BRK%20B");
  expect(parseHash(formatRoute(r), "home")).toEqual(r);
});
```

`frontend/src/pages/smart/ConsensusTab.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import ConsensusTab from "./ConsensusTab";
import { resolveSmartTab } from "../SmartMoneyPage";

afterEach(() => vi.restoreAllMocks());

test("resolveSmartTab: param, then saved, then managers", () => {
  expect(resolveSmartTab(["funds"], "consensus")).toBe("funds");
  expect(resolveSmartTab(["bogus"], "consensus")).toBe("consensus");
  expect(resolveSmartTab([], null)).toBe("managers");
});

test("consensus rows show held-by counts and manager names", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    managers: [{ label: "buffett", period_of_report: "2026-06-30" }, { label: "ackman", period_of_report: "2026-03-31" }, { label: "loeb", period_of_report: null }],
    rows: [{ issuer: "ALPHABET INC", cusip: "02079K305", manager_count: 2, total_value_usd: 5e9, combined_weight_pct: 12.34,
      weights_pct: { buffett: 2.1, ackman: 10.24 } }],
  })));
  render(<FluentProvider theme={webDarkTheme}><ConsensusTab /></FluentProvider>);
  await waitFor(() => expect(screen.getByText("ALPHABET INC")).toBeTruthy());
  expect(screen.getByText("2 of 3")).toBeTruthy();
  expect(screen.getByText("buffett, ackman")).toBeTruthy();
  expect(screen.getByText("$5.00B")).toBeTruthy();
  expect(screen.getByText("Consensus across 3 managers")).toBeTruthy();
});
```

- [ ] **Step 2: Run to see them fail** — `npx vitest run src/lib/route src/pages/smart/ConsensusTab` — FAIL.

- [ ] **Step 3: Implement `route.ts` changes**

```ts
export type Route = { kind: "page"; page: PageId; params?: string[] } | { kind: "stock"; symbol: string; tab: StockTab };

// in parseHash, replace the final two lines with:
  if (!parts.length || !(PAGE_IDS as string[]).includes(parts[0])) return { kind: "page", page: fallback };
  const params = parts.slice(1);
  return params.length ? { kind: "page", page: parts[0] as PageId, params } : { kind: "page", page: parts[0] as PageId };

export function formatRoute(r: Route): string {
  if (r.kind === "stock") return `#/stock/${encodeURIComponent(r.symbol)}/${r.tab}`;
  return `#/${r.page}${r.params?.length ? "/" + r.params.map(encodeURIComponent).join("/") : ""}`;
}
```

- [ ] **Step 4: API additions** exactly as in Interfaces. **CommandBox**: replace the `/classic` line with the `go(...)` call above.

- [ ] **Step 5: Implement `SmartMoneyPage.tsx` and `ConsensusTab.tsx`**

`frontend/src/pages/SmartMoneyPage.tsx`:
```tsx
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
```

`frontend/src/pages/smart/ConsensusTab.tsx`:
```tsx
import { Button, Caption1, Dropdown, Option } from "@fluentui/react-components";
import { useState } from "react";
import { useApi } from "../../lib/useApi";
import { api, type ConsensusRow } from "../../lib/api";
import { fmtMoney, fmtNum } from "../../lib/fmt";
import { downloadCsv } from "../../lib/csv";
import Block from "../../blocks/Block";
import DataTable, { tableCsv, type Column } from "../../components/DataTable";

export default function ConsensusTab() {
  const [min, setMin] = useState(2);
  const { data, error, loading, fetchedAt } = useApi(`consensus:${min}`, () => api.consensus(min, 25));
  const n = data?.managers.length ?? 0;
  const cols: Column<ConsensusRow>[] = [
    { key: "i", label: "Issuer", render: (r) => r.issuer, csv: (r) => r.issuer },
    { key: "h", label: "Held by", align: "right", render: (r) => <span className="num" style={{ color: "var(--up)" }}>{`${r.manager_count} of ${n}`}</span>, csv: (r) => r.manager_count },
    { key: "m", label: "Managers", render: (r) => <span title={Object.entries(r.weights_pct).map(([k, v]) => `${k}: ${v.toFixed(1)}%`).join("\n")}>{Object.keys(r.weights_pct).join(", ")}</span>, csv: (r) => Object.keys(r.weights_pct).join(" ") },
    { key: "w", label: "Combined weight", align: "right", render: (r) => <span className="num">{`${fmtNum(r.combined_weight_pct, 1)}%`}</span>, csv: (r) => r.combined_weight_pct },
    { key: "v", label: "Total value", align: "right", render: (r) => <span className="num">{fmtMoney(r.total_value_usd)}</span>, csv: (r) => r.total_value_usd },
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span>Held by at least</span>
        <Dropdown size="small" value={String(min)} selectedOptions={[String(min)]} onOptionSelect={(_, d) => setMin(Number(d.optionValue))} aria-label="Minimum managers">
          {[2, 3, 4, 5].map((m) => <Option key={m} value={String(m)}>{String(m)}</Option>)}
        </Dropdown>
        <span>managers</span>
      </div>
      <Block fixed sec title={data ? `Consensus across ${n} managers` : "Consensus"} loading={loading} error={error} fetchedAt={fetchedAt}
        actions={data?.rows.length ? <Button size="small" onClick={() => downloadCsv("consensus.csv", tableCsv(cols, data.rows))}>Export CSV</Button> : undefined}>
        {!data && !error && <span style={{ color: "var(--dim)" }}>Comparing every tracked manager's latest 13F (first run maps tickers; can take a minute)…</span>}
        {data && (
          <>
            <Caption1 style={{ color: "var(--dim)" }}>{data.managers.map((m) => m.label).join(" / ")}</Caption1>
            <DataTable columns={cols} rows={data.rows} rowKey={(r) => r.cusip} empty="No overlapping positions found." />
          </>
        )}
      </Block>
    </div>
  );
}
```

In `App.tsx` add `smart` to `PAGES` (pass `params`). If `PAGES` entries can't see `route`, change the map's value type to `(params: string[]) => JSX.Element` and call `PAGES[route.page]?.(route.params ?? [])`.

- [ ] **Step 6: Run tests, typecheck, build** — `npx vitest run`, `npx tsc --noEmit`, `npm run build`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/route.ts frontend/src/lib/route.test.ts frontend/src/lib/api.ts frontend/src/shell/CommandBox.tsx frontend/src/App.tsx frontend/src/pages/SmartMoneyPage.tsx frontend/src/pages/smart
git add -A src/howlet/static/app
git commit -m "Frontend: Smart Money page shell, consensus tab, page route params"
```

---

### Task 2: Managers tab (13F portfolio, allocation, Q/Q changes, news)

**Files:**
- Create: `frontend/src/components/ManagerPicker.tsx`, `frontend/src/pages/smart/ManagersTab.tsx`
- Modify: `frontend/src/pages/SmartMoneyPage.tsx` (route `managers`)
- Test: `frontend/src/pages/smart/ManagersTab.test.tsx`

**Interfaces:**
- Consumes: `api.portfolio`, `api.diff`, `api.newsFor`, `api.managers`, types `Portfolio`, `PortfolioPosition`, `DiffChange` (`api.ts`); `useApi`; `useRoute`; `Block`; `DataTable`, `tableCsv`; `downloadCsv`; `Ticker`; `Sparkline`; `NewsList`; `fmtMoney`, `fmtNum`, `fmtInt`, `signed`, `tone`.
- Produces:
  - `ManagerPicker({ value, onPick })` — Fluent `Combobox` with `freeform`, options = `/api/managers` labels; pressing Enter or choosing an option calls `onPick(text.trim().toLowerCase())` when non-empty; placeholder "Manager or CIK".
  - `ManagersTab({ manager })` (`manager` = `params[1]` or `"buffett"`) — a ManagerPicker whose `onPick(m)` does `go({ kind: "page", page: "smart", params: ["managers", m] })`, then four independent panels:
    1. **Holdings** (`api.portfolio(manager, 25)`, `Block fixed sec`): header line `CIK {cik} · period {period_of_report} · filed {filing_date} · {position_count} positions · {fmtMoney(total_value_usd)}`; columns # (index+1, dim) / Ticker (`Ticker`) / Issuer / Price / %Chg (signed, toned, "—" when null) / 1M (`Sparkline` 70×16) / Value (`fmtMoney`) / Shares (`fmtInt`, dim) / Weight (`fmtNum(weight_pct, 1)%`). CSV `${manager}-portfolio.csv`. Loading hint "Loading the latest 13F (the first load of a manager maps tickers and can take ~30s)…".
    2. **Allocation** (same response): top 10 positions as rows of label (ticker else issuer) + a bar `width = weight / max(top-10 weight) * 100%` filled with `var(--accent)` + `x.x%`. Empty "No positions.".
    3. **Q/Q changes** (`api.diff(manager)`, `Block fixed sec`): sub-caption `{prior_period} → {current_period}`; first 40 changes: status `Badge` (NEW success, INCREASED success, DECREASED warning, SOLD danger), Issuer, Value change (`signed`-style: `+`/`-` + `fmtMoney(abs)`, toned), Shares change (`signed(shares_change, 0)`, dim). CSV `${manager}-changes.csv`. Empty "No changes between the last two filings.".
    4. **News** (`api.newsFor(first 8 non-null tickers of the portfolio, 25)`, refresh 300 000; only once the portfolio has loaded — key `null` until then): `NewsList`, title `News · {tickers joined ", "}`, empty "No headlines right now.".
  - Panels are laid out in a 2-column grid: Holdings spans both columns; Allocation, Q/Q changes and News fill the rest.

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/smart/ManagersTab.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import ManagersTab from "./ManagersTab";

afterEach(() => vi.restoreAllMocks());
const json = (b: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(b), { status }));

test("holdings, allocation, changes load; diff failure shows its SEC error alone", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const u = String(input);
    if (u.startsWith("/api/managers")) return json([{ label: "buffett", cik: "1067983" }]);
    if (u.startsWith("/api/portfolio")) return json({ identifier: "buffett", cik: "0001067983", period_of_report: "2026-06-30",
      filing_date: "2026-08-14", accession_number: "a", total_value_usd: 3e11, position_count: 2, positions: [
        { issuer: "APPLE INC", cusip: "037833100", value_usd: 6.6e10, shares: 227917808, share_type: "SH", weight_pct: 22.04, ticker: "AAPL", price: 347.73, change_pct: -0.14, currency: "USD", sparkline: [1, 2] },
        { issuer: "OBSCURE CO", cusip: "999999999", value_usd: 1e6, shares: 10, share_type: "SH", weight_pct: 0.01, ticker: null, price: null, change_pct: null, currency: null, sparkline: [] },
      ] });
    if (u.startsWith("/api/diff")) return json({ error: "Need 2 filings to diff" }, 404);
    return json([]);
  });
  render(<FluentProvider theme={webDarkTheme}><ManagersTab manager="buffett" /></FluentProvider>);
  await waitFor(() => expect(screen.getAllByText("APPLE INC").length).toBeGreaterThan(0));
  expect(screen.getByText(/CIK 0001067983 · period 2026-06-30 · filed 2026-08-14 · 2 positions · \$300\.00B/)).toBeTruthy();
  expect(screen.getAllByText("22.0%").length).toBeGreaterThan(0);
  expect(screen.getAllByText("OBSCURE CO").length).toBeGreaterThan(0); // allocation falls back to issuer
  await waitFor(() => expect(screen.getByText("Need 2 filings to diff")).toBeTruthy());
});
```

- [ ] **Step 2: Run to see it fail.**

- [ ] **Step 3: Implement `ManagerPicker.tsx`**

```tsx
import { Combobox, Option } from "@fluentui/react-components";
import { useState } from "react";
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";

export default function ManagerPicker({ value, onPick }: { value: string; onPick: (m: string) => void }) {
  const { data } = useApi("managers", api.managers);
  const [text, setText] = useState(value);
  const commit = (v: string) => { const m = v.trim().toLowerCase(); if (m) onPick(m); };
  return (
    <Combobox freeform size="small" placeholder="Manager or CIK" value={text} aria-label="Manager or CIK"
      onChange={(e) => setText((e.target as HTMLInputElement).value)}
      onOptionSelect={(_, d) => { if (d.optionValue) { setText(d.optionValue); commit(d.optionValue); } }}
      onKeyDown={(e) => { if (e.key === "Enter") commit(text); }}>
      {(data ?? []).map((m) => <Option key={m.cik} value={m.label}>{m.label}</Option>)}
    </Combobox>
  );
}
```

- [ ] **Step 4: Implement `ManagersTab.tsx`**

```tsx
import { Badge, Button, Caption1 } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type DiffChange, type PortfolioPosition } from "../../lib/api";
import { fmtInt, fmtMoney, fmtNum, signed, tone } from "../../lib/fmt";
import { downloadCsv } from "../../lib/csv";
import { useRoute } from "../../lib/route";
import Block from "../../blocks/Block";
import DataTable, { tableCsv, type Column } from "../../components/DataTable";
import Ticker from "../../components/Ticker";
import Sparkline from "../../components/Sparkline";
import NewsList from "../../components/NewsList";
import ManagerPicker from "../../components/ManagerPicker";

const FIVE_MIN = 300_000;
const STATUS = { NEW: "success", INCREASED: "success", DECREASED: "warning", SOLD: "danger" } as const;
const num = (s: string, style?: React.CSSProperties) => <span className="num" style={style}>{s}</span>;
const usdChange = (v: number) => `${v >= 0 ? "+" : "-"}${fmtMoney(Math.abs(v))}`;

const HOLD_COLS: Column<PortfolioPosition & { i: number }>[] = [
  { key: "n", label: "#", render: (r) => <span style={{ color: "var(--dim)" }}>{r.i + 1}</span>, csv: (r) => r.i + 1 },
  { key: "t", label: "Ticker", render: (r) => <Ticker symbol={r.ticker} />, csv: (r) => r.ticker },
  { key: "is", label: "Issuer", render: (r) => r.issuer, csv: (r) => r.issuer },
  { key: "p", label: "Price", align: "right", render: (r) => num(fmtNum(r.price)), csv: (r) => r.price },
  { key: "c", label: "%Chg", align: "right", render: (r) => num(r.change_pct == null ? "—" : `${signed(r.change_pct)}%`, { color: tone(r.change_pct) }), csv: (r) => r.change_pct },
  { key: "s", label: "1M", render: (r) => <Sparkline values={r.sparkline} w={70} h={16} /> },
  { key: "v", label: "Value", align: "right", render: (r) => num(fmtMoney(r.value_usd)), csv: (r) => r.value_usd },
  { key: "sh", label: "Shares", align: "right", render: (r) => num(fmtInt(r.shares), { color: "var(--dim)" }), csv: (r) => r.shares },
  { key: "w", label: "Weight", align: "right", render: (r) => num(`${fmtNum(r.weight_pct, 1)}%`), csv: (r) => r.weight_pct },
];

const CHANGE_COLS: Column<DiffChange>[] = [
  { key: "s", label: "Status", render: (r) => <Badge size="small" appearance="tint" color={STATUS[r.status as keyof typeof STATUS] ?? "informative"}>{r.status}</Badge>, csv: (r) => r.status },
  { key: "i", label: "Issuer", render: (r) => r.issuer, csv: (r) => r.issuer },
  { key: "v", label: "Value change", align: "right", render: (r) => num(usdChange(r.value_change_usd), { color: tone(r.value_change_usd) }), csv: (r) => r.value_change_usd },
  { key: "sh", label: "Shares change", align: "right", render: (r) => num(signed(r.shares_change, 0), { color: "var(--dim)" }), csv: (r) => r.shares_change },
];

export default function ManagersTab({ manager }: { manager: string }) {
  const go = useRoute((r) => r.go);
  const port = useApi(`portfolio:${manager}`, () => api.portfolio(manager, 25));
  const diff = useApi(`diff:${manager}`, () => api.diff(manager));
  const tickers = (port.data?.positions ?? []).map((p) => p.ticker).filter((t): t is string => !!t).slice(0, 8);
  const news = useApi(port.data ? `mgrnews:${manager}:${tickers.join(",")}` : null, () => api.newsFor(tickers, 25), FIVE_MIN);
  const rows = (port.data?.positions ?? []).map((p, i) => ({ ...p, i }));
  const top = rows.slice(0, 10);
  const maxW = Math.max(...top.map((p) => p.weight_pct), 0.0001);
  const d = port.data;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ width: 260 }}>
        <ManagerPicker key={manager} value={manager} onPick={(m) => go({ kind: "page", page: "smart", params: ["managers", m] })} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12, alignItems: "start" }}>
        <div style={{ gridColumn: "1 / -1" }}>
          <Block fixed sec title={`Holdings · ${manager}`} loading={port.loading} error={port.error} fetchedAt={port.fetchedAt}
            actions={rows.length ? <Button size="small" onClick={() => downloadCsv(`${manager}-portfolio.csv`, tableCsv(HOLD_COLS, rows))}>Export CSV</Button> : undefined}>
            {!d && !port.error && <span style={{ color: "var(--dim)" }}>Loading the latest 13F (the first load of a manager maps tickers and can take ~30s)…</span>}
            {d && (
              <>
                <Caption1 style={{ color: "var(--dim)" }}>{`CIK ${d.cik} · period ${d.period_of_report ?? "?"} · filed ${d.filing_date ?? "?"} · ${d.position_count} positions · ${fmtMoney(d.total_value_usd)}`}</Caption1>
                <DataTable columns={HOLD_COLS} rows={rows} rowKey={(r) => r.cusip} empty="No positions." />
              </>
            )}
          </Block>
        </div>
        <Block fixed sec title="Allocation · top 10" loading={port.loading} error={port.error} fetchedAt={port.fetchedAt}>
          {d && (top.length ? top.map((p) => (
            <div key={p.cusip} style={{ display: "grid", gridTemplateColumns: "110px 1fr 56px", gap: 8, alignItems: "center", padding: "2px 0" }}>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.ticker ?? p.issuer}</span>
              <span style={{ background: "var(--elev-1)", height: 10, borderRadius: 3 }}>
                <span style={{ display: "block", height: "100%", width: `${(p.weight_pct / maxW) * 100}%`, background: "var(--accent)", borderRadius: 3 }} />
              </span>
              <span className="num" style={{ textAlign: "right" }}>{`${fmtNum(p.weight_pct, 1)}%`}</span>
            </div>
          )) : <span style={{ color: "var(--dim)" }}>No positions.</span>)}
        </Block>
        <Block fixed sec title="Q/Q changes" loading={diff.loading} error={diff.error} fetchedAt={diff.fetchedAt}
          actions={diff.data?.changes.length ? <Button size="small" onClick={() => downloadCsv(`${manager}-changes.csv`, tableCsv(CHANGE_COLS, diff.data!.changes))}>Export CSV</Button> : undefined}>
          {diff.data && (
            <>
              <Caption1 style={{ color: "var(--dim)" }}>{`${diff.data.prior_period ?? "?"} → ${diff.data.current_period ?? "?"}`}</Caption1>
              <DataTable columns={CHANGE_COLS} rows={diff.data.changes.slice(0, 40)} rowKey={(r) => r.cusip} empty="No changes between the last two filings." />
            </>
          )}
        </Block>
        <Block fixed title={tickers.length ? `News · ${tickers.join(", ")}` : "News"} loading={news.loading} error={news.error} fetchedAt={news.fetchedAt} refreshMs={FIVE_MIN}>
          {news.data && <NewsList items={news.data} empty="No headlines right now." />}
        </Block>
      </div>
    </div>
  );
}
```
(If `DiffChange` isn't exported from `api.ts`, export it — it already exists as a type there.) In `SmartMoneyPage.tsx` render `<ManagersTab manager={params[1] ?? "buffett"} />` for the managers tab.

- [ ] **Step 5: Run tests, typecheck, build.**

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ManagerPicker.tsx frontend/src/pages/smart/ManagersTab.tsx frontend/src/pages/smart/ManagersTab.test.tsx frontend/src/pages/SmartMoneyPage.tsx frontend/src/lib/api.ts
git add -A src/howlet/static/app
git commit -m "Frontend: Smart Money managers tab (holdings, allocation, Q/Q changes, news)"
```

---

### Task 3: Insider buys and Position history tabs

**Files:**
- Create: `frontend/src/pages/smart/InsiderBuysTab.tsx`, `frontend/src/pages/smart/PositionHistoryTab.tsx`
- Modify: `frontend/src/pages/SmartMoneyPage.tsx`
- Test: `frontend/src/pages/smart/InsiderBuysTab.test.tsx`, `frontend/src/pages/smart/PositionHistoryTab.test.tsx`

**Interfaces:**
- Consumes: `api.insiderBuys`, `api.positionHistory`, types `InsiderBuy`, `PositionQuarter`; `getWatchlists` (`lib/legacy.ts`); `ManagerPicker` (Task 2); `useApi`; `useRoute`; `Block`; `DataTable`; `Ticker`; `fmtInt`, `fmtMoney`, `fmtNum`.
- Produces:
  - `stockSymbols(list: string[]): string[]` (exported from `InsiderBuysTab.tsx`) — drops symbols that start with `^` or contain `=` or `-USD` (indices, FX, futures, crypto have no Form 4s; classic rule).
  - `InsiderBuysTab()` — a watchlist `Dropdown` (names from `getWatchlists()`, default `"default"` if present else the first); symbols = `stockSymbols(list).slice(0, 15)`; no symbols → "Add stock symbols to this watchlist (Portfolio → Watchlists) to screen them." and no request. Otherwise `api.insiderBuys(symbols, 8)` keyed `ibuys:${symbols.join(",")}` in a `Block fixed sec` titled "Open-market insider buys"; while loading with no data: `Scanning Form 4s for ${symbols.length} symbols (first run is the slow one)…`; summary chips per `summary` row `${symbol} ${buy_count}× ${fmtMoney(total_value_usd)}` (green text); table of `buys` (first 50): Date (raw, "?" if null) / Symbol (`Ticker`) / Insider (`title` = relationship) / Shares (`fmtInt`) / Price (`fmtNum`) / Value (`fmtMoney`); empty: `No open-market insider buys across ${symbols.join(", ")} in their last 8 Form 4s each. (Insider buying is rare — that's why it matters.)`.
  - `PositionHistoryTab({ manager, query })` (from `params[1]`, `params[2]`) — a ManagerPicker + a Fluent `Input` "Ticker, CUSIP or name" + **Show** button (Enter also runs); running does `go({ kind: "page", page: "smart", params: ["history", manager, query] })`. When both are present: `api.positionHistory(manager, query, 8)` keyed `phist:${manager}:${query}` in a `Block fixed sec` titled `${issuer} · CUSIP ${cusips.join(", ")}` (else "Position history"); rows oldest first: Period (raw) / Value (`fmtMoney` + a bar `value / max(values) * 100%` in `var(--accent)`) / Shares (`fmtInt`, plus a delta vs the previous quarter when different: `(+N)` green / `(-N)` red, none on the first row) / Weight (`fmtNum(weight_pct, 1)%`). Server 404 text shows (e.g. "didn't report anything matching …"). Without both inputs show "Pick a manager and a security to see their stake quarter by quarter.".

- [ ] **Step 1: Write the failing tests**

`frontend/src/pages/smart/InsiderBuysTab.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import InsiderBuysTab, { stockSymbols } from "./InsiderBuysTab";

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

test("stockSymbols drops indices, FX, futures and crypto", () => {
  expect(stockSymbols(["AAPL", "^GSPC", "EURUSD=X", "CL=F", "BTC-USD", "BRK-B"])).toEqual(["AAPL", "BRK-B"]);
});

test("scans the default list's stock symbols and renders buys", async () => {
  localStorage.setItem("howlet_watchlists_v1", JSON.stringify({ default: ["AAPL", "^GSPC", "MSFT"] }));
  const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    symbols_scanned: ["AAPL", "MSFT"], filings_per_symbol: 8,
    summary: [{ symbol: "MSFT", buy_count: 2, total_shares: 100, total_value_usd: 2e6, latest_date: "2026-10-01" }],
    buys: [{ symbol: "MSFT", insider: "Jane Doe", relationship: "Director", date: "2026-10-01", shares: 50, price_per_share: 400,
      value_usd: 20000, shares_owned_after: 1000, filing_date: "2026-10-02", accession_number: "x" }],
  })));
  render(<FluentProvider theme={webDarkTheme}><InsiderBuysTab /></FluentProvider>);
  await waitFor(() => expect(screen.getByText("Jane Doe")).toBeTruthy());
  expect(String(f.mock.calls[0][0])).toContain("symbols=AAPL%2CMSFT");
  expect(screen.getByText("MSFT 2× $2.0M")).toBeTruthy();
});
```

`frontend/src/pages/smart/PositionHistoryTab.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import PositionHistoryTab from "./PositionHistoryTab";

afterEach(() => vi.restoreAllMocks());

test("quarters render oldest first with share deltas", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    if (String(input).startsWith("/api/managers")) return Promise.resolve(new Response("[]"));
    return Promise.resolve(new Response(JSON.stringify({ identifier: "buffett", cik: "1", query: "AAPL", issuer: "APPLE INC", cusips: ["037833100"],
      quarters: [
        { period_of_report: "2025-12-31", filing_date: "2026-02-17", shares: 300, value_usd: 3e10, weight_pct: 25, held: true },
        { period_of_report: "2026-03-31", filing_date: "2026-05-15", shares: 250, value_usd: 2e10, weight_pct: 20, held: true },
      ] })));
  });
  render(<FluentProvider theme={webDarkTheme}><PositionHistoryTab manager="buffett" query="AAPL" /></FluentProvider>);
  await waitFor(() => expect(screen.getByText("APPLE INC · CUSIP 037833100")).toBeTruthy());
  expect(screen.getByText("2025-12-31")).toBeTruthy();
  expect(screen.getByText("(-50)")).toBeTruthy();
  expect(screen.getByText("25.0%")).toBeTruthy();
});
```

- [ ] **Step 2: Run to see them fail.**

- [ ] **Step 3: Implement both tabs** to the Interfaces above, reusing `DataTable` for the buys table and a plain `<table className="dt">` for history (rows need the per-row delta). Route `insiders` → `<InsiderBuysTab />` and `history` → `<PositionHistoryTab manager={params[1] ?? ""} query={params[2] ?? ""} />` in `SmartMoneyPage.tsx`. Use `getWatchlists` from `lib/legacy.ts`; `safeHref` is not needed here.

- [ ] **Step 4: Run tests, typecheck, build.**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/smart/InsiderBuysTab.tsx frontend/src/pages/smart/InsiderBuysTab.test.tsx frontend/src/pages/smart/PositionHistoryTab.tsx frontend/src/pages/smart/PositionHistoryTab.test.tsx frontend/src/pages/SmartMoneyPage.tsx
git add -A src/howlet/static/app
git commit -m "Frontend: Smart Money insider-buys screen and position history"
```

---

### Task 4: Filing search and Funds tabs

**Files:**
- Create: `frontend/src/pages/smart/FilingSearchTab.tsx`, `frontend/src/pages/smart/FundsTab.tsx`
- Modify: `frontend/src/pages/SmartMoneyPage.tsx` (route `search`, `funds`; remove the now-unused `PlaceholderPage` import)
- Test: `frontend/src/pages/smart/FilingSearchTab.test.tsx`

**Interfaces:**
- Consumes: `api.fulltext`, `api.fund`, types `FullTextHit`, `FundHolding`; `useApi`; `useRoute`; `Block`; `DataTable`, `tableCsv`; `downloadCsv`; `safeHref`; `fmtMoney`, `fmtNum`.
- Produces:
  - `parseForms(s: string): string[]` (exported) — splits on commas/whitespace, upper-cases, drops empties ("10-k, 8-K" → `["10-K", "8-K"]`).
  - `FilingSearchTab({ query, forms })` (from `params[1]`, `params[2]`) — `Input` "Words or a quoted phrase (e.g. \"share repurchase\")", `Input` "Forms (optional, e.g. 10-K, 8-K)", **Search** button / Enter → `go({ kind: "page", page: "smart", params: ["search", query, formsText] })` (omit the third param when blank). When `query` is non-empty: `api.fulltext(query, parseForms(forms), 25)` keyed `fts:${query}:${forms}`; `Block fixed sec` titled `Full-text search · "${query}"`; columns Filed (`file_date` raw) / Company / Form / Document (link via `safeHref(url)` with text `file_description || file_type || "document"`). Empty "No filings matched.". Caption under the inputs: "EDGAR full-text search covers filings since 2001.".
  - `FundsTab({ symbol })` (from `params[1]`) — `Input` "ETF or mutual fund ticker" + **Load** / Enter → `go({ ..., params: ["funds", SYMBOL] })`. When set: `api.fund(symbol, 50)` keyed `fund:${symbol}`; `Block fixed sec` titled `${fund}` (else "Fund holdings"), caption `as of ${report_period_date ?? "?"} · net assets ${fmtMoney(net_assets)} · ${position_count} positions`; columns Holding (`name`, `title` attribute = `title`) / Value (`fmtMoney`) / % of fund (`fmtNum(pct_val, 2)%`) / Asset (`asset_cat ?? "—"`) / Country (`country ?? "—"`); CSV `${symbol}-holdings.csv`; empty "No holdings reported."; server errors (e.g. no N-PORT for SPY, a unit investment trust) show via `sec`. Caption under the input: "Funds report holdings monthly on SEC Form N-PORT. Unit investment trusts such as SPY don't file it.".

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/smart/FilingSearchTab.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import FilingSearchTab, { parseForms } from "./FilingSearchTab";

afterEach(() => vi.restoreAllMocks());

test("parseForms normalises the forms list", () => {
  expect(parseForms(" 10-k, 8-K  def 14a")).toEqual(["10-K", "8-K", "DEF", "14A"]);
  expect(parseForms("")).toEqual([]);
});

test("results render with safe document links and raw dates", async () => {
  const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ query: "x", forms: ["8-K"], results: [
    { accession_number: "a", cik: "1", company: "ACME CORP", file_date: "2025-03-01", file_description: "Press release", file_type: "EX-99", form: "8-K", url: "https://www.sec.gov/x.htm" },
    { accession_number: "b", cik: "2", company: "EVIL INC", file_date: "2025-03-02", file_description: null, file_type: "EX-1", form: "8-K", url: "javascript:alert(1)" },
  ] })));
  render(<FluentProvider theme={webDarkTheme}><FilingSearchTab query="share repurchase" forms="8-K" /></FluentProvider>);
  await waitFor(() => expect(screen.getByText("ACME CORP")).toBeTruthy());
  expect(String(f.mock.calls[0][0])).toContain("forms=8-K");
  expect(screen.getByText("2025-03-01")).toBeTruthy();
  expect(screen.getByText("Press release").closest("a")?.getAttribute("href")).toBe("https://www.sec.gov/x.htm");
  expect(screen.getByText("EX-1").closest("a")?.getAttribute("href") ?? null).toBeNull(); // Fluent Link w/o href renders a <button>
});
```
(Note `parseForms` splits on whitespace too, so "DEF 14A" must be typed as "DEF-14A"-style or one token by users; the test documents the rule. Keep it simple.)

- [ ] **Step 2: Run to see it fail.**

- [ ] **Step 3: Implement both tabs** to the Interfaces; route `search` → `<FilingSearchTab query={params[1] ?? ""} forms={params[2] ?? ""} />`, `funds` → `<FundsTab symbol={(params[1] ?? "").toUpperCase()} />`; remove `PlaceholderPage` from `SmartMoneyPage.tsx`.

- [ ] **Step 4: Run tests, typecheck, build.**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/smart/FilingSearchTab.tsx frontend/src/pages/smart/FilingSearchTab.test.tsx frontend/src/pages/smart/FundsTab.tsx frontend/src/pages/SmartMoneyPage.tsx
git add -A src/howlet/static/app
git commit -m "Frontend: Smart Money full-text filing search and fund holdings"
```

---

### Task 5: Portfolio page — watchlists

**Files:**
- Create: `frontend/src/lib/watchlists.ts`, `frontend/src/pages/PortfolioPage.tsx`, `frontend/src/pages/portfolio/WatchlistsTab.tsx`
- Modify: `frontend/src/App.tsx` (route `portfolio`), `frontend/src/blocks/WatchlistBlock.tsx` (empty-list hint)
- Test: `frontend/src/lib/watchlists.test.ts`

**Interfaces:**
- Consumes: `getWatchlists` (`lib/legacy.ts`); `writeJson`, `readJson`; `api.quotes`, `api.newsFor`, `api.events`; `useApi`; `REFRESH_MS`, `useSettings`; `Block`; `DataTable`; `Ticker`; `Sparkline`; `NewsList`; `stockSymbols` (Task 3); `fmtNum`, `fmtInt`, `signed`, `tone`.
- Produces:
  - `watchlists.ts` (pure; never mutates its input): `type Watchlists = Record<string, string[]>`; `WATCHLISTS_KEY = "howlet_watchlists_v1"`; `addSymbol(all, list, raw): Watchlists` (trim + upper-case; ignore empty or duplicate); `removeSymbol(all, list, sym)`; `createList(all, raw): { all: Watchlists; name: string } | { error: string }` (trim + lower-case; "Name the list." when empty; "That list already exists." when taken); `deleteList(all, name): Watchlists` (returns `all` unchanged when it is the only list); `saveWatchlists(all)` → `writeJson(WATCHLISTS_KEY, all)` (same shape the classic page reads).
  - `PortfolioPage({ params })` — header row with an account `Dropdown` showing one option "Manual holdings" (and caption "Paper trading and Schwab accounts arrive in a later update."), then a `TabList` Watchlists / Holdings & risk; tab from `params[0]` else `howlet_portfolio_tab_v1` else `"watchlists"`; switching does `go({ kind: "page", page: "portfolio", params: [tab] })`. Holdings & risk renders `PlaceholderPage` until Task 6.
  - `WatchlistsTab()` — state `all` (from `getWatchlists()`) and `list` (default `"default"` if present else first). Controls: list `Dropdown`; "New list" `Input` + **Create**; **Delete list** which first turns into **Confirm delete** (second click deletes; disabled for the only list); "Add symbol" `Input` + **Add** (Enter works). Every change saves via `saveWatchlists`. Three panels:
    1. **Quotes** (`api.quotes(symbols)` at the refresh speed; key `null` when empty → "Empty list — add a symbol above."): columns ✕ remove button (`aria-label` "Remove SYM") / Symbol (`Ticker`) / Name (dim) / Price / %Chg (signed, toned, "—" for null) / 5D (`Sparkline` 70×14) / Day range (`low – high`) / Volume (`fmtInt`). Symbols with no quote still get a row showing "no data".
    2. **News** (`api.newsFor(stockSymbols(symbols).slice(0, 10), 40)`, refresh 300 000; none → "Add stock symbols to see scoped news.").
    3. **Upcoming events** — for `stockSymbols(symbols).slice(0, 12)`, fetch `api.events(sym)` **one at a time** (sequential; SEC proxy lookups are throttled) into a module-level `Map<string, Events>` cache shared across mounts; render progressively after each symbol: Symbol (`Ticker`) / Next earnings (raw, "—") / Analysts ("—") / Last proxy (`DEF 14A ${shareholder_meetings[0].filing_date}` or "—"); a failed symbol shows "unavailable". Cancel the loop on unmount/list change.
  - `WatchlistBlock.tsx` empty hint becomes "Empty list — add symbols on the Portfolio page.".

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/watchlists.test.ts`:
```ts
import { addSymbol, createList, deleteList, removeSymbol, saveWatchlists, WATCHLISTS_KEY } from "./watchlists";

beforeEach(() => localStorage.clear());

test("add/remove normalise, dedupe and never mutate", () => {
  const all = { default: ["AAPL"] };
  const a = addSymbol(all, "default", " msft ");
  expect(a.default).toEqual(["AAPL", "MSFT"]);
  expect(all.default).toEqual(["AAPL"]);
  expect(addSymbol(a, "default", "aapl")).toBe(a);
  expect(addSymbol(a, "default", "  ")).toBe(a);
  expect(removeSymbol(a, "default", "AAPL").default).toEqual(["MSFT"]);
});

test("create and delete lists", () => {
  const r = createList({ default: [] }, " Tech ");
  expect(r).toEqual({ all: { default: [], tech: [] }, name: "tech" });
  expect(createList({ default: [] }, "DEFAULT")).toEqual({ error: "That list already exists." });
  expect(createList({ default: [] }, " ")).toEqual({ error: "Name the list." });
  expect(deleteList({ default: [], tech: [] }, "tech")).toEqual({ default: [] });
  const only = { default: ["A"] };
  expect(deleteList(only, "default")).toBe(only);
});

test("save writes the classic shape", () => {
  saveWatchlists({ default: ["AAPL"] });
  expect(JSON.parse(localStorage.getItem(WATCHLISTS_KEY)!)).toEqual({ default: ["AAPL"] });
});
```

- [ ] **Step 2: Run to see it fail.**

- [ ] **Step 3: Implement `watchlists.ts`**

```ts
import { writeJson } from "./storage";

export type Watchlists = Record<string, string[]>;
export const WATCHLISTS_KEY = "howlet_watchlists_v1"; // shared with the classic page; same shape

export function addSymbol(all: Watchlists, list: string, raw: string): Watchlists {
  const sym = raw.trim().toUpperCase();
  const cur = all[list] ?? [];
  if (!sym || cur.includes(sym)) return all;
  return { ...all, [list]: [...cur, sym] };
}

export const removeSymbol = (all: Watchlists, list: string, sym: string): Watchlists =>
  ({ ...all, [list]: (all[list] ?? []).filter((s) => s !== sym) });

export function createList(all: Watchlists, raw: string): { all: Watchlists; name: string } | { error: string } {
  const name = raw.trim().toLowerCase();
  if (!name) return { error: "Name the list." };
  if (name in all) return { error: "That list already exists." };
  return { all: { ...all, [name]: [] }, name };
}

export function deleteList(all: Watchlists, name: string): Watchlists {
  if (Object.keys(all).length <= 1 || !(name in all)) return all;
  const { [name]: _gone, ...rest } = all;
  return rest;
}

export const saveWatchlists = (all: Watchlists) => writeJson(WATCHLISTS_KEY, all);
```

- [ ] **Step 4: Implement `PortfolioPage.tsx` and `WatchlistsTab.tsx`** to the Interfaces. Route `portfolio` in `App.tsx` (pass params like `smart`). Update the WatchlistBlock hint.

- [ ] **Step 5: Run tests, typecheck, build.** (The WatchlistBlock test asserts `/Empty list/` — it still matches.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/watchlists.ts frontend/src/lib/watchlists.test.ts frontend/src/pages/PortfolioPage.tsx frontend/src/pages/portfolio frontend/src/App.tsx frontend/src/blocks/WatchlistBlock.tsx
git add -A src/howlet/static/app
git commit -m "Frontend: Portfolio page with editable watchlists, news and events"
```

---

### Task 6: Holdings & risk, docs and live pass

**Files:**
- Create: `frontend/src/lib/holdings.ts`, `frontend/src/pages/portfolio/HoldingsTab.tsx`
- Modify: `frontend/src/pages/PortfolioPage.tsx` (route the tab; drop `PlaceholderPage`), `CLAUDE.md`
- Test: `frontend/src/lib/holdings.test.ts`, `frontend/src/pages/portfolio/HoldingsTab.test.tsx`

**Interfaces:**
- Consumes: `readJson`, `writeJson`; `api.risk`, `Risk`, `RiskPosition`; `useApi`; `Block`; `DataTable`; `Ticker`; `fmtInt`, `fmtNum`, `signed`, `tone`.
- Produces:
  - `holdings.ts`: `type Holding = { symbol: string; shares: number }`; `HOLDINGS_KEY = "howlet_pf_holdings"`; `loadHoldings(): Holding[]` (array of valid `{symbol: string, shares: finite > 0}` entries only; anything else → `[]` / skipped); `upsertHolding(list, rawSymbol, shares): Holding[] | { error: string }` — trim/upper symbol ("Enter a symbol." when empty), shares must be finite and > 0 ("Shares must be a positive number."); an existing symbol has its shares **replaced** (classic behaviour), otherwise appended; `removeHolding(list, symbol)`; `saveHoldings(list)` → `writeJson(HOLDINGS_KEY, list)`.
  - `HoldingsTab()` — add form (Symbol `Input`, Shares `Input` `inputMode="decimal"`, **Add / update**; errors via Fluent `Field` validation); holdings table (Symbol `Ticker` / Shares `fmtInt` / ✕ remove with `aria-label` "Remove SYM"); empty "No positions yet — add one above." Caption "Saved in this browser — not a 13F filing.". **Risk** `Block fixed` (non-`sec`; it's computed from Yahoo prices): no holdings → "Add positions to compute risk." and no request; else `api.risk(holdings, "1y")` keyed `risk:${JSON.stringify(holdings)}`; loading "Fetching price history and computing risk…"; a 200 response with `error` and no positions shows that error text; otherwise stat rows — Return (1y) `signed(portfolio_return_pct, 1)%` toned, Annualised volatility `fmtNum(…, 1)%`, Max drawdown `fmtNum(…, 1)%` toned, Sharpe (rf = 0) `fmtNum(sharpe_ratio)` ("—" for null) — and a table Symbol / Weight / Return / Volatility / Max DD (1dp %, return and DD toned).
  - `CLAUDE.md` Status: extend the React status line with "Smart Money (managers, consensus, insider buys, position history, full-text search, funds) and Portfolio (watchlists, holdings & risk) pages (2026-10-24)".

- [ ] **Step 1: Write the failing tests**

`frontend/src/lib/holdings.test.ts`:
```ts
import { HOLDINGS_KEY, loadHoldings, removeHolding, saveHoldings, upsertHolding } from "./holdings";

beforeEach(() => localStorage.clear());

test("load keeps only valid entries", () => {
  localStorage.setItem(HOLDINGS_KEY, JSON.stringify([{ symbol: "AAPL", shares: 10 }, { symbol: "X", shares: -1 }, null, { symbol: 5 }]));
  expect(loadHoldings()).toEqual([{ symbol: "AAPL", shares: 10 }]);
  localStorage.setItem(HOLDINGS_KEY, "{}");
  expect(loadHoldings()).toEqual([]);
});

test("upsert replaces shares, validates input; remove; save shape", () => {
  const a = upsertHolding([], " aapl ", 10) as { symbol: string; shares: number }[];
  expect(a).toEqual([{ symbol: "AAPL", shares: 10 }]);
  expect(upsertHolding(a, "AAPL", 5)).toEqual([{ symbol: "AAPL", shares: 5 }]);
  expect(upsertHolding(a, "", 5)).toEqual({ error: "Enter a symbol." });
  expect(upsertHolding(a, "MSFT", 0)).toEqual({ error: "Shares must be a positive number." });
  expect(upsertHolding(a, "MSFT", NaN)).toEqual({ error: "Shares must be a positive number." });
  expect(removeHolding(a, "AAPL")).toEqual([]);
  saveHoldings(a);
  expect(JSON.parse(localStorage.getItem(HOLDINGS_KEY)!)).toEqual([{ symbol: "AAPL", shares: 10 }]);
});
```

`frontend/src/pages/portfolio/HoldingsTab.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import HoldingsTab from "./HoldingsTab";

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

test("POSTs holdings and renders the risk summary", async () => {
  localStorage.setItem("howlet_pf_holdings", JSON.stringify([{ symbol: "AAPL", shares: 10 }]));
  const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    portfolio_return_pct: 12.34, portfolio_annualized_volatility_pct: 25.1, portfolio_max_drawdown_pct: -18.2, sharpe_ratio: 0.87,
    positions: [{ symbol: "AAPL", weight_pct: 100, return_pct: 12.34, annualized_volatility_pct: 25.1, max_drawdown_pct: -18.2 }],
  })));
  render(<FluentProvider theme={webDarkTheme}><HoldingsTab /></FluentProvider>);
  await waitFor(() => expect(screen.getAllByText("+12.3%").length).toBeGreaterThan(0));
  const [url, init] = f.mock.calls[0];
  expect(url).toBe("/api/risk");
  expect(JSON.parse(String((init as RequestInit).body))).toEqual({ holdings: [{ symbol: "AAPL", shares: 10 }], range: "1y" });
  expect(screen.getByText("0.87")).toBeTruthy();
});

test("no holdings: hint and no request", () => {
  const f = vi.spyOn(globalThis, "fetch");
  render(<FluentProvider theme={webDarkTheme}><HoldingsTab /></FluentProvider>);
  expect(screen.getByText("Add positions to compute risk.")).toBeTruthy();
  expect(f).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run to see them fail.**

- [ ] **Step 3: Implement `holdings.ts` and `HoldingsTab.tsx`** to the Interfaces; route the tab in `PortfolioPage.tsx` and remove `PlaceholderPage` there. Update `CLAUDE.md` as stated (one line, nothing else).

- [ ] **Step 4: Run everything** — `npx vitest run`, `npx tsc --noEmit`, `npm run build`; from repo root `PYTHONPATH=src pytest tests/ -q` and `ruff check src/ tests/`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/holdings.ts frontend/src/lib/holdings.test.ts frontend/src/pages/portfolio/HoldingsTab.tsx frontend/src/pages/portfolio/HoldingsTab.test.tsx frontend/src/pages/PortfolioPage.tsx CLAUDE.md
git add -A src/howlet/static/app
git commit -m "Frontend: Portfolio holdings and risk; docs"
```

- [ ] **Step 6: Live pass (controller)** at `http://localhost:8813/`:
  1. Ctrl+K `buffett` lands on `#/smart/managers/buffett` (not `/classic`); holdings, allocation, Q/Q changes, news; switch manager via the picker (try `ackman` and a raw CIK); CSV exports.
  2. Consensus with min 2/3; Insider buys from the default watchlist; Position history `buffett` + `AAPL` (8 quarters, share deltas); Filing search `"share repurchase"` with form `8-K`; Funds `ARKK` (and `SPY` shows the server's N-PORT error).
  3. Portfolio → Watchlists: create a list, add/remove symbols, delete it; the change shows in `/classic` MY and in the Home watchlist block. Events fill in one symbol at a time.
  4. Holdings & risk: add AAPL 10 and MSFT 5; risk summary computes; the classic PF screen shows the same holdings.
  5. Back/forward through sub-tabs restores tab + manager; console clean.
