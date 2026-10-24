# Howlet React pages 2a: News, Markets, Screener — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the classic NEWS, MKTS (stocks/crypto), FX matrix, ECO and EQS screens into the React app as the News, Markets (Stocks / Crypto / FX / Economy sub-tabs) and Screener rail pages, on shared formatting and table components.

**Architecture:** Plan 2 of the redesign spec (`docs/superpowers/specs/2026-10-23-react-redesign-design.md`) is split in four: **2a** (this: shared components + News/Markets/Screener), 2b (stock page tabs: chart, financials, holders, news, options), 2c (Smart Money + Portfolio pages), 2d (remaining Home blocks, Home tabs/snapshots, Help, backend additions, delete `/classic`). The classic-screen inventory with every field and route is `docs/superpowers/plans/classic-inventory.md` (cited below as "inventory §N"). No Python changes in 2a.

**Tech Stack:** as plan 1 — React 18, TypeScript, Vite 5, Fluent UI v9, zustand, Vitest + Testing Library.

## Global Constraints

- No change to `views.py`, the MCP server, the CLI, any `/api/*` route, or `src/howlet/dashboard.html`.
- Colour hex literals only in `frontend/src/theme/tokens.ts`. Up/down/dim colours come from `var(--up)`, `var(--down)`, `var(--dim)`.
- Fonts: system only; numbers use the `.num` class (`var(--font-mono)` + tabular figures).
- Classic localStorage keys are read, never rewritten in an incompatible shape. New state in new keys only (`howlet_markets_tab_v1`).
- Market, news, crypto and FX failures degrade quietly ("Unavailable, retrying" from `Block`); SEC-backed panels (screener uses SEC fundamentals) may show the server's error text.
- Date-only strings (`publication_date`, `filing_date`, `period_of_report`) are shown raw, never through `new Date(...)` (CLAUDE.md gotcha: they'd render a day early in US timezones). ISO timestamps (`published`) may use `Date`.
- External links render only when the URL starts with `http://` or `https://`.
- Each page panel loads independently: one failing request never leaves another panel stuck on "Loading".
- Run frontend commands from `frontend/`; Python tests from repo root with `PYTHONPATH=src pytest tests/ -q`. Build with `npm run build` and commit `src/howlet/static/app` (stage with `git add -A src/howlet/static/app`) in every task that changes UI.
- Verify live at `http://localhost:8813/` (not the Vite dev origin).

## File structure

```
frontend/src/
  lib/fmt.ts              # fmtNum, fmtInt, fmtMoney, signed, tone, priceDigits, ago, safeHref
  lib/csv.ts              # toCsv, downloadCsv
  lib/screener.ts         # buildScreenerQuery (pure)
  lib/api.ts              # + markets, crypto, fx, macro, fedEvents, regulatory, screener (+ types)
  components/Sparkline.tsx, Ticker.tsx, DataTable.tsx, NewsList.tsx
  blocks/Block.tsx        # + `fixed` and `actions` props
  blocks/NewsBlock.tsx    # now renders <NewsList>
  pages/NewsPage.tsx
  pages/MarketsPage.tsx
  pages/markets/StocksTab.tsx, CryptoTab.tsx, FxTab.tsx, EconomyTab.tsx
  pages/ScreenerPage.tsx
  index.css               # + .num, .dt table styles
  App.tsx                 # route news/markets/screener to the new pages
```

---

### Task 1: Formatting, CSV and shared display components

**Files:**
- Create: `frontend/src/lib/fmt.ts`, `frontend/src/lib/csv.ts`, `frontend/src/components/Sparkline.tsx`, `frontend/src/components/Ticker.tsx`, `frontend/src/components/DataTable.tsx`, `frontend/src/components/NewsList.tsx`
- Modify: `frontend/src/blocks/Block.tsx` (add `fixed`, `actions`), `frontend/src/blocks/NewsBlock.tsx` (use `NewsList`), `frontend/src/index.css` (add `.num` and `.dt` styles)
- Test: `frontend/src/lib/fmt.test.ts`, `frontend/src/lib/csv.test.ts`, `frontend/src/components/DataTable.test.tsx`

**Interfaces:**
- Consumes: `useRoute` (`lib/route.ts`), `NewsItem` type (`lib/api.ts`: `{title, link, source, symbol: string|null, published: string|null}`).
- Produces:
  - `fmt.ts`: `fmtNum(n: number|null|undefined, digits = 2): string` ("—" for null/NaN, `en-US` locale, fixed digits); `fmtInt(n): string`; `fmtMoney(usd): string` ($x.xxT / $x.xxB / $x.xM / $x,xxx, leading "-" for negatives, "—" for null); `signed(n, digits = 2): string` ("+" prefix when > 0); `tone(n): string` → `"var(--up)" | "var(--down)" | "var(--dim)"`; `priceDigits(p): number` (4 when |p| < 1 else 2); `ago(iso: string|null, now = Date.now()): string` ("" for null, "5m", "3h", "2d"); `safeHref(url: string|null|undefined): string|undefined` (only http/https).
  - `csv.ts`: `toCsv(header: string[], rows: (string|number|null|undefined)[][]): string` (RFC 4180 quoting, CRLF); `downloadCsv(filename: string, csv: string): void`.
  - `Sparkline({ values?: number[]; w?: number; h?: number })`.
  - `Ticker({ symbol })` — link that opens the stock page; "—" when empty; stops click propagation.
  - `DataTable<T>({ columns: Column<T>[]; rows: T[]; rowKey: (r: T) => string; empty: string; onRowClick?: (r: T) => void })`, `type Column<T> = { key: string; label: string; align?: "left"|"right"; render: (r: T) => ReactNode; csv?: (r: T) => string|number|null }`, `tableCsv<T>(columns, rows): string`.
  - `NewsList({ items: NewsItem[]; empty: string })` — title link (safe href, new tab, `rel="noopener noreferrer"`), meta line `source · SYMBOL · 3h`.
  - `Block` gains `fixed?: boolean` (no drag handle / grab cursor; used on pages) and `actions?: ReactNode` (rendered before the spinner/remove button).

- [ ] **Step 1: Write the failing tests**

`frontend/src/lib/fmt.test.ts`:
```ts
import { ago, fmtInt, fmtMoney, fmtNum, priceDigits, safeHref, signed, tone } from "./fmt";

test("fmtNum / fmtInt", () => {
  expect(fmtNum(1234.5)).toBe("1,234.50");
  expect(fmtNum(0.12345, 4)).toBe("0.1235");
  expect(fmtNum(null)).toBe("—");
  expect(fmtNum(NaN)).toBe("—");
  expect(fmtInt(1234567.4)).toBe("1,234,567");
  expect(fmtInt(undefined)).toBe("—");
});

test("fmtMoney scales and signs", () => {
  expect(fmtMoney(1.5e12)).toBe("$1.50T");
  expect(fmtMoney(2.345e9)).toBe("$2.35B");
  expect(fmtMoney(-95e6)).toBe("-$95.0M");
  expect(fmtMoney(12345)).toBe("$12,345");
  expect(fmtMoney(null)).toBe("—");
});

test("signed, tone, priceDigits", () => {
  expect(signed(1.234)).toBe("+1.23");
  expect(signed(-1.2, 1)).toBe("-1.2");
  expect(signed(0)).toBe("0.00");
  expect(signed(null)).toBe("—");
  expect(tone(2)).toBe("var(--up)");
  expect(tone(-2)).toBe("var(--down)");
  expect(tone(0)).toBe("var(--dim)");
  expect(tone(null)).toBe("var(--dim)");
  expect(priceDigits(0.9991)).toBe(4);
  expect(priceDigits(80728)).toBe(2);
});

test("ago and safeHref", () => {
  const now = Date.parse("2026-10-24T12:00:00Z");
  expect(ago("2026-10-24T11:55:00Z", now)).toBe("5m");
  expect(ago("2026-10-24T09:00:00Z", now)).toBe("3h");
  expect(ago("2026-10-22T12:00:00Z", now)).toBe("2d");
  expect(ago(null, now)).toBe("");
  expect(safeHref("https://x.com/a")).toBe("https://x.com/a");
  expect(safeHref("javascript:alert(1)")).toBeUndefined();
  expect(safeHref(null)).toBeUndefined();
});
```

`frontend/src/lib/csv.test.ts`:
```ts
import { toCsv } from "./csv";

test("quotes commas, quotes and newlines; nulls are empty", () => {
  const csv = toCsv(["a", "b"], [["x,y", 'say "hi"'], [null, 3], ["line\nbreak", undefined]]);
  expect(csv).toBe('a,b\r\n"x,y","say ""hi"""\r\n,3\r\n"line\nbreak",');
});
```

`frontend/src/components/DataTable.test.tsx`:
```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import DataTable, { tableCsv, type Column } from "./DataTable";

type R = { s: string; v: number };
const cols: Column<R>[] = [
  { key: "s", label: "SYM", render: (r) => r.s, csv: (r) => r.s },
  { key: "v", label: "VAL", align: "right", render: (r) => r.v.toFixed(1), csv: (r) => r.v },
];

test("renders headers, rows, and row clicks", () => {
  const click = vi.fn();
  render(<DataTable columns={cols} rows={[{ s: "A", v: 1 }, { s: "B", v: 2 }]} rowKey={(r) => r.s} empty="none" onRowClick={click} />);
  expect(screen.getByText("SYM")).toBeTruthy();
  fireEvent.click(screen.getByText("B"));
  expect(click).toHaveBeenCalledWith({ s: "B", v: 2 });
});

test("empty rows show the empty text", () => {
  render(<DataTable columns={cols} rows={[]} rowKey={(r) => r.s} empty="Nothing here." />);
  expect(screen.getByText("Nothing here.")).toBeTruthy();
});

test("tableCsv uses labels and csv accessors", () => {
  expect(tableCsv(cols, [{ s: "A", v: 1.5 }])).toBe("SYM,VAL\r\nA,1.5");
});
```

- [ ] **Step 2: Run to see them fail**

Run: `npx vitest run src/lib/fmt src/lib/csv src/components/DataTable`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement `fmt.ts` and `csv.ts`**

`frontend/src/lib/fmt.ts`:
```ts
type N = number | null | undefined;
const bad = (n: N): n is null | undefined => n == null || Number.isNaN(n);

export const fmtNum = (n: N, digits = 2): string =>
  bad(n) ? "—" : n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const fmtInt = (n: N): string => (bad(n) ? "—" : Math.round(n).toLocaleString("en-US"));

export function fmtMoney(usd: N): string {
  if (bad(usd)) return "—";
  const a = Math.abs(usd), s = usd < 0 ? "-" : "";
  if (a >= 1e12) return `${s}$${(a / 1e12).toFixed(2)}T`;
  if (a >= 1e9) return `${s}$${(a / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${s}$${(a / 1e6).toFixed(1)}M`;
  return `${s}$${fmtInt(a)}`;
}

export const signed = (n: N, digits = 2): string => (bad(n) ? "—" : `${n > 0 ? "+" : ""}${fmtNum(n, digits)}`);

export const tone = (n: N): string => (bad(n) || n === 0 ? "var(--dim)" : n > 0 ? "var(--up)" : "var(--down)");

export const priceDigits = (p: N): number => (!bad(p) && Math.abs(p) < 1 ? 4 : 2);

export function ago(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const m = Math.max(0, Math.round((now - t) / 60000));
  return m < 60 ? `${m}m` : m < 1440 ? `${Math.round(m / 60)}h` : `${Math.round(m / 1440)}d`;
}

export const safeHref = (url: string | null | undefined): string | undefined =>
  url && /^https?:\/\//i.test(url) ? url : undefined;
```

`frontend/src/lib/csv.ts`:
```ts
type Cell = string | number | null | undefined;

const cell = (v: Cell): string => {
  const s = v == null ? "" : String(v);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export const toCsv = (header: string[], rows: Cell[][]): string =>
  [header, ...rows].map((r) => r.map(cell).join(",")).join("\r\n");

export function downloadCsv(filename: string, csv: string): void {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
```

- [ ] **Step 4: Implement the components**

`frontend/src/components/Sparkline.tsx`:
```tsx
export default function Sparkline({ values, w = 70, h = 16 }: { values?: number[]; w?: number; h?: number }) {
  if (!values || values.length < 2) return null;
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * w).toFixed(1)},${(h - ((v - min) / span) * h).toFixed(1)}`).join(" ");
  const up = values[values.length - 1] >= values[0];
  return (
    <svg width={w} height={h} aria-hidden="true" style={{ display: "block" }}>
      <polyline points={pts} fill="none" strokeWidth={1.2} stroke={up ? "var(--up)" : "var(--down)"} />
    </svg>
  );
}
```

`frontend/src/components/Ticker.tsx`:
```tsx
import { Link } from "@fluentui/react-components";
import { useRoute } from "../lib/route";

export default function Ticker({ symbol }: { symbol: string | null | undefined }) {
  const go = useRoute((r) => r.go);
  if (!symbol) return <span style={{ color: "var(--dim)" }}>—</span>;
  return (
    <Link onClick={(e) => { e.stopPropagation(); go({ kind: "stock", symbol, tab: "overview" }); }}>{symbol}</Link>
  );
}
```

`frontend/src/components/DataTable.tsx`:
```tsx
import type { ReactNode } from "react";
import { toCsv } from "../lib/csv";

export type Column<T> = {
  key: string; label: string; align?: "left" | "right";
  render: (r: T) => ReactNode; csv?: (r: T) => string | number | null;
};

type Props<T> = { columns: Column<T>[]; rows: T[]; rowKey: (r: T) => string; empty: string; onRowClick?: (r: T) => void };

export default function DataTable<T>({ columns, rows, rowKey, empty, onRowClick }: Props<T>) {
  if (!rows.length) return <div style={{ color: "var(--dim)", padding: "4px 0" }}>{empty}</div>;
  return (
    <table className="dt">
      <thead>
        <tr>{columns.map((c) => <th key={c.key} style={{ textAlign: c.align ?? "left" }}>{c.label}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={rowKey(r)} onClick={onRowClick ? () => onRowClick(r) : undefined} style={onRowClick ? { cursor: "pointer" } : undefined}>
            {columns.map((c) => <td key={c.key} style={{ textAlign: c.align ?? "left" }}>{c.render(r)}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export const tableCsv = <T,>(columns: Column<T>[], rows: T[]): string =>
  toCsv(columns.map((c) => c.label), rows.map((r) => columns.map((c) => (c.csv ? c.csv(r) : ""))));
```

`frontend/src/components/NewsList.tsx`:
```tsx
import { Link } from "@fluentui/react-components";
import type { NewsItem } from "../lib/api";
import { ago, safeHref } from "../lib/fmt";

export default function NewsList({ items, empty }: { items: NewsItem[]; empty: string }) {
  if (!items.length) return <div style={{ color: "var(--dim)" }}>{empty}</div>;
  return (
    <>
      {items.map((n, i) => (
        <div key={`${n.link}-${i}`} style={{ padding: "5px 0", borderBottom: "1px solid var(--hair)" }}>
          <Link href={safeHref(n.link)} target="_blank" rel="noopener noreferrer">{n.title}</Link>
          <div style={{ color: "var(--dim)", fontSize: "0.85em" }}>
            {[n.source, n.symbol, ago(n.published)].filter(Boolean).join(" · ")}
          </div>
        </div>
      ))}
    </>
  );
}
```

- [ ] **Step 5: `Block` props, `NewsBlock`, CSS**

In `frontend/src/blocks/Block.tsx`: add `fixed?: boolean; actions?: ReactNode;` to `Props`, destructure them, and change the header to:
```tsx
      <CardHeader className={fixed ? undefined : "drag-handle"} style={fixed ? undefined : { cursor: "grab" }}
```
and render `{actions}` as the first child inside the existing `action={<span ...>` wrapper (before the spinner).

Replace the body of `frontend/src/blocks/NewsBlock.tsx`'s returned `Block` children (the `data?.map(...)` list and its local `ago` helper) with:
```tsx
      {data && <NewsList items={data} empty="No headlines right now." />}
```
importing `NewsList from "../components/NewsList"` and deleting the local `ago` function and the now-unused `Link`/`safeHref` logic.

Append to `frontend/src/index.css`:
```css
.num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
.dt { width: 100%; border-collapse: collapse; }
.dt th { color: var(--dim); font-weight: 600; font-size: 0.85em; text-align: left; padding: 4px 6px;
  border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--panel); }
.dt td { padding: 4px 6px; border-bottom: 1px solid var(--hair); }
.dt tbody tr:hover td { background: var(--elev-1); }
```

- [ ] **Step 6: Run tests, typecheck, build**

Run: `npx vitest run`, `npx tsc --noEmit`, `npm run build`
Expected: all pass; build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/fmt.ts frontend/src/lib/fmt.test.ts frontend/src/lib/csv.ts frontend/src/lib/csv.test.ts frontend/src/components frontend/src/blocks/Block.tsx frontend/src/blocks/NewsBlock.tsx frontend/src/index.css
git add -A src/howlet/static/app
git commit -m "Frontend: shared formatters, CSV, DataTable, NewsList, Sparkline, Ticker"
```

---

### Task 2: API additions and the News page

**Files:**
- Modify: `frontend/src/lib/api.ts` (types + 7 wrappers), `frontend/src/App.tsx` (route `news`)
- Create: `frontend/src/pages/NewsPage.tsx`
- Test: `frontend/src/pages/NewsPage.test.tsx`

**Interfaces:**
- Consumes: `getJson`, `NewsItem` (`api.ts`); `useApi`; `Block` (`fixed`); `NewsList`.
- Produces (in `api.ts`, field names verified against the live server 2026-10-24):
```ts
export type MarketRow = { symbol: string; label: string; price: number; change_pct: number | null; sparkline: number[] };
export type MarketSection = { section: string; rows: MarketRow[] };
export type CryptoRow = { rank: number; symbol: string; name: string; price: number; change_pct_24h: number | null;
  market_cap: number | null; volume_24h: number | null; high_24h: number | null; low_24h: number | null };
export type CryptoResult = { source: string; rows: CryptoRow[] };
export type FxResult = { date?: string; currencies?: string[]; matrix?: Record<string, Record<string, number>> };
export type BlsPoint = { value: string; period: string; year: string };
export type MacroResult = {
  treasury_yield_curve: { date?: string; curve?: { maturity: string; yield_pct: number }[] } | null;
  bls_series: Record<string, BlsPoint[]> | null;
  fred_available: boolean;
  fred_series: Record<string, { description: string; latest: number | string | null; date: string | null }> | null;
};
export type RegDoc = { title: string; type: string | null; document_number: string; html_url: string; publication_date: string | null };
export type ScreenerRow = { symbol: string; price: number | null; change_pct: number | null; market_cap: number | null;
  pe_ratio: number | null; eps_diluted: number | null; revenue: number | null; revenue_growth_pct: number | null; net_margin_pct: number | null };
export type ScreenerResult = { universe_size: number; matched: number; rows: ScreenerRow[] };
```
and in the `api` object:
```ts
  markets: () => getJson<MarketSection[]>("/api/markets"),
  crypto: (limit = 50) => getJson<CryptoResult>(`/api/crypto?limit=${limit}`),
  fx: () => getJson<FxResult>("/api/fx"),
  macro: () => getJson<MacroResult>("/api/macro"),
  fedEvents: (limit = 15) => getJson<NewsItem[]>(`/api/fed-events?limit=${limit}`),
  regulatory: (limit = 15) => getJson<RegDoc[]>(`/api/regulatory?limit=${limit}`),
  screener: (qs: string) => getJson<ScreenerResult>(`/api/screener?${qs}`),
```
  Fed events have no `symbol`: `fedEvents` maps nothing — `NewsList` already tolerates a missing `symbol` (it's filtered out of the meta line).
- `NewsPage()`: three independent panels — **Market wire** (`api.news(60)`), **Earnings & analysis** (the same wire response filtered to `source` matching `/CNBC Earnings|Seeking Alpha/`, first 15), **Fed & policy** (`api.fedEvents(15)`). All refresh every 300 000 ms. Empty texts (inventory §3): "No headlines right now.", "Nothing tagged earnings/analysis in the current wire.", "No Fed items right now.".

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/NewsPage.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import NewsPage from "./NewsPage";

afterEach(() => vi.restoreAllMocks());

test("wire, earnings filter and fed panel load independently", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.startsWith("/api/fed-events")) return Promise.resolve(new Response("{}", { status: 502 }));
    return Promise.resolve(new Response(JSON.stringify([
      { title: "Wire story", link: "https://a/1", source: "Yahoo Finance", symbol: null, published: null },
      { title: "Beat and raise", link: "https://a/2", source: "CNBC Earnings", symbol: null, published: null },
    ])));
  });
  render(<FluentProvider theme={webDarkTheme}><NewsPage /></FluentProvider>);
  await waitFor(() => expect(screen.getAllByText("Beat and raise")).toHaveLength(2)); // wire + earnings
  expect(screen.getByText("Wire story")).toBeTruthy();
  await waitFor(() => expect(screen.getByText("Unavailable, retrying")).toBeTruthy()); // fed failed quietly
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npx vitest run src/pages/NewsPage`
Expected: FAIL — module not found.

- [ ] **Step 3: Add the API types/wrappers above to `api.ts`, then implement `NewsPage.tsx`**

```tsx
import { useApi } from "../lib/useApi";
import { api } from "../lib/api";
import Block from "../blocks/Block";
import NewsList from "../components/NewsList";

const FIVE_MIN = 300_000;
const EARNINGS = /CNBC Earnings|Seeking Alpha/;

export default function NewsPage() {
  const wire = useApi("news:60", () => api.news(60), FIVE_MIN);
  const fed = useApi("fed:15", () => api.fedEvents(15), FIVE_MIN);
  const earnings = (wire.data ?? []).filter((n) => EARNINGS.test(n.source)).slice(0, 15);
  const half = "calc((100vh - 120px) / 2)";
  return (
    <div style={{ padding: 16, display: "grid", gridTemplateColumns: "minmax(0, 3fr) minmax(0, 2fr)", gap: 12 }}>
      <div style={{ height: "calc(100vh - 108px)" }}>
        <Block fixed title="Market wire" loading={wire.loading} error={wire.error} fetchedAt={wire.fetchedAt} refreshMs={FIVE_MIN}>
          {wire.data && <NewsList items={wire.data} empty="No headlines right now." />}
        </Block>
      </div>
      <div style={{ display: "grid", gridTemplateRows: `${half} ${half}`, gap: 12 }}>
        <Block fixed title="Earnings & analysis" loading={wire.loading} error={wire.error} fetchedAt={wire.fetchedAt} refreshMs={FIVE_MIN}>
          {wire.data && <NewsList items={earnings} empty="Nothing tagged earnings/analysis in the current wire." />}
        </Block>
        <Block fixed title="Fed & policy" loading={fed.loading} error={fed.error} fetchedAt={fed.fetchedAt} refreshMs={FIVE_MIN}>
          {fed.data && <NewsList items={fed.data} empty="No Fed items right now." />}
        </Block>
      </div>
    </div>
  );
}
```

In `App.tsx` add `import NewsPage from "./pages/NewsPage";` and in the page switch render `<NewsPage />` when `route.page === "news"` (keep the existing `home` and `settings` branches; `PlaceholderPage` stays the fallback).

- [ ] **Step 4: Run tests, typecheck, build**

Run: `npx vitest run`, `npx tsc --noEmit`, `npm run build` — all green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/pages/NewsPage.tsx frontend/src/pages/NewsPage.test.tsx frontend/src/App.tsx
git add -A src/howlet/static/app
git commit -m "Frontend: News page (wire, earnings & analysis, Fed & policy)"
```

---

### Task 3: Markets page — Stocks and Crypto tabs

**Files:**
- Create: `frontend/src/pages/MarketsPage.tsx`, `frontend/src/pages/markets/StocksTab.tsx`, `frontend/src/pages/markets/CryptoTab.tsx`
- Modify: `frontend/src/App.tsx` (route `markets`)
- Test: `frontend/src/pages/MarketsPage.test.tsx`

**Interfaces:**
- Consumes: `api.markets`, `api.crypto`, types `MarketSection`, `CryptoRow` (Task 2); `useApi`; `REFRESH_MS`, `useSettings`; `readJson`, `writeJson`; `Block` (`fixed`, `actions`); `DataTable`; `Ticker`; `Sparkline`; `fmtNum`, `fmtMoney`, `signed`, `tone`, `priceDigits`.
- Produces:
  - `type MarketsTab = "stocks" | "crypto" | "fx" | "economy"`; `MARKETS_TAB_KEY = "howlet_markets_tab_v1"`; `initialMarketsTab(): MarketsTab` — reads the new key; if absent, maps classic `howlet_mkts_mode` (`"crypto"` → `"crypto"`, anything else → `"stocks"`). Never writes `howlet_mkts_mode`.
  - `MarketsPage()` — Fluent `TabList` (Stocks / Crypto / FX / Economy), remembers the choice in `howlet_markets_tab_v1`. FX and Economy render `PlaceholderPage` until Task 4.
  - `StocksTab()` — `api.markets` refreshed at the user's refresh speed; one `Block fixed` per section in a `repeat(auto-fill, minmax(320px, 1fr))` grid; each row: `Ticker`, label (dim), price (`.num`), `signed(change_pct)%` coloured by `tone`, `Sparkline` 60×14. Loading text "Loading world markets (30+ instruments)…".
  - `CryptoTab()` — `api.crypto(50)` at the refresh speed; one `Block fixed` titled "Crypto · top N by market cap · 24h" with `actions` showing `source: <source>`; `DataTable` columns `#`, Coin (`symbol` + dim `name`), Price (`$` + `fmtNum(price, priceDigits(price))`), 24h % (signed, toned), Mkt cap (`fmtMoney`), 24h volume (`fmtMoney`), 24h low / high (`priceDigits`; "—" when `low_24h` is null). Empty rows: "Crypto data unavailable right now (CoinGecko and Coinpaprika both unreachable).". Rows are not clickable (inventory §6).

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/MarketsPage.test.tsx`:
```tsx
import { initialMarketsTab, MARKETS_TAB_KEY } from "./MarketsPage";

beforeEach(() => localStorage.clear());

test("new key wins; otherwise classic mode maps; never writes the classic key", () => {
  expect(initialMarketsTab()).toBe("stocks");
  localStorage.setItem("howlet_mkts_mode", "crypto");
  expect(initialMarketsTab()).toBe("crypto");
  localStorage.setItem(MARKETS_TAB_KEY, JSON.stringify("economy"));
  expect(initialMarketsTab()).toBe("economy");
  localStorage.setItem(MARKETS_TAB_KEY, JSON.stringify("bogus"));
  expect(initialMarketsTab()).toBe("crypto");
  expect(localStorage.getItem("howlet_mkts_mode")).toBe("crypto");
});
```

- [ ] **Step 2: Run to see it fail**

Run: `npx vitest run src/pages/MarketsPage` — FAIL, module not found.

- [ ] **Step 3: Implement**

`frontend/src/pages/MarketsPage.tsx`:
```tsx
import { Tab, TabList } from "@fluentui/react-components";
import { useState } from "react";
import { readJson, writeJson } from "../lib/storage";
import StocksTab from "./markets/StocksTab";
import CryptoTab from "./markets/CryptoTab";
import PlaceholderPage from "./PlaceholderPage";

export type MarketsTab = "stocks" | "crypto" | "fx" | "economy";
const TABS: [MarketsTab, string][] = [["stocks", "Stocks"], ["crypto", "Crypto"], ["fx", "FX"], ["economy", "Economy"]];
export const MARKETS_TAB_KEY = "howlet_markets_tab_v1";
const isTab = (v: unknown): v is MarketsTab => TABS.some(([t]) => t === v);

export function initialMarketsTab(): MarketsTab {
  const saved = readJson<MarketsTab | null>(MARKETS_TAB_KEY, null, (v): v is MarketsTab => isTab(v));
  if (saved) return saved;
  let classic: string | null = null;
  try { classic = localStorage.getItem("howlet_mkts_mode"); } catch { /* storage blocked */ }
  return classic === "crypto" ? "crypto" : "stocks";
}

export default function MarketsPage() {
  const [tab, setTab] = useState<MarketsTab>(initialMarketsTab);
  const pick = (t: MarketsTab) => { setTab(t); writeJson(MARKETS_TAB_KEY, t); };
  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <TabList selectedValue={tab} onTabSelect={(_, d) => pick(d.value as MarketsTab)}>
        {TABS.map(([t, label]) => <Tab key={t} value={t}>{label}</Tab>)}
      </TabList>
      {tab === "stocks" && <StocksTab />}
      {tab === "crypto" && <CryptoTab />}
      {tab === "fx" && <PlaceholderPage title="FX" />}
      {tab === "economy" && <PlaceholderPage title="Economy" />}
    </div>
  );
}
```

`frontend/src/pages/markets/StocksTab.tsx`:
```tsx
import { useApi } from "../../lib/useApi";
import { api } from "../../lib/api";
import { REFRESH_MS, useSettings } from "../../lib/settings";
import { fmtNum, signed, tone } from "../../lib/fmt";
import Block from "../../blocks/Block";
import Ticker from "../../components/Ticker";
import Sparkline from "../../components/Sparkline";

export default function StocksTab() {
  const refreshMs = REFRESH_MS[useSettings((s) => s.settings.refresh)];
  const { data, error, loading, fetchedAt } = useApi("markets", api.markets, refreshMs);
  if (!data) {
    return (
      <Block fixed title="World markets" loading={loading} error={error} fetchedAt={fetchedAt} refreshMs={refreshMs}>
        {!error && <span style={{ color: "var(--dim)" }}>Loading world markets (30+ instruments)…</span>}
      </Block>
    );
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 12 }}>
      {data.map((sec) => (
        <Block fixed key={sec.section} title={sec.section} error={error} fetchedAt={fetchedAt} refreshMs={refreshMs}>
          <table className="dt">
            <tbody>
              {sec.rows.map((r) => (
                <tr key={r.symbol}>
                  <td><Ticker symbol={r.symbol} /></td>
                  <td style={{ color: "var(--dim)" }}>{r.label}</td>
                  <td className="num" style={{ textAlign: "right" }}>{fmtNum(r.price)}</td>
                  <td className="num" style={{ textAlign: "right", color: tone(r.change_pct) }}>{r.change_pct == null ? "—" : `${signed(r.change_pct)}%`}</td>
                  <td><Sparkline values={r.sparkline} w={60} h={14} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Block>
      ))}
    </div>
  );
}
```

`frontend/src/pages/markets/CryptoTab.tsx`:
```tsx
import { Caption1 } from "@fluentui/react-components";
import { useApi } from "../../lib/useApi";
import { api, type CryptoRow } from "../../lib/api";
import { REFRESH_MS, useSettings } from "../../lib/settings";
import { fmtMoney, fmtNum, priceDigits, signed, tone } from "../../lib/fmt";
import Block from "../../blocks/Block";
import DataTable, { type Column } from "../../components/DataTable";

const px = (p: number | null) => (p == null ? "—" : `$${fmtNum(p, priceDigits(p))}`);

const COLS: Column<CryptoRow>[] = [
  { key: "rank", label: "#", render: (r) => <span style={{ color: "var(--dim)" }}>{r.rank}</span> },
  { key: "coin", label: "Coin", render: (r) => <><b>{r.symbol}</b> <span style={{ color: "var(--dim)" }}>{r.name}</span></> },
  { key: "price", label: "Price", align: "right", render: (r) => <span className="num">{px(r.price)}</span> },
  { key: "chg", label: "24h %", align: "right", render: (r) => <span className="num" style={{ color: tone(r.change_pct_24h) }}>{r.change_pct_24h == null ? "—" : `${signed(r.change_pct_24h)}%`}</span> },
  { key: "cap", label: "Mkt cap", align: "right", render: (r) => <span className="num">{fmtMoney(r.market_cap)}</span> },
  { key: "vol", label: "24h volume", align: "right", render: (r) => <span className="num">{fmtMoney(r.volume_24h)}</span> },
  { key: "range", label: "24h low / high", align: "right", render: (r) => <span className="num">{r.low_24h == null ? "—" : `${px(r.low_24h)} / ${px(r.high_24h)}`}</span> },
];

export default function CryptoTab() {
  const refreshMs = REFRESH_MS[useSettings((s) => s.settings.refresh)];
  const { data, error, loading, fetchedAt } = useApi("crypto:50", () => api.crypto(50), refreshMs);
  return (
    <Block fixed title={`Crypto · top ${data?.rows.length ?? 50} by market cap · 24h`} loading={loading} error={error}
      fetchedAt={fetchedAt} refreshMs={refreshMs} actions={data?.source ? <Caption1 style={{ color: "var(--dim)" }}>source: {data.source}</Caption1> : undefined}>
      {data && <DataTable columns={COLS} rows={data.rows} rowKey={(r) => r.symbol}
        empty="Crypto data unavailable right now (CoinGecko and Coinpaprika both unreachable)." />}
    </Block>
  );
}
```

In `App.tsx` add `import MarketsPage from "./pages/MarketsPage";` and render it when `route.page === "markets"`.

- [ ] **Step 4: Run tests, typecheck, build** — `npx vitest run`, `npx tsc --noEmit`, `npm run build`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/MarketsPage.tsx frontend/src/pages/MarketsPage.test.tsx frontend/src/pages/markets frontend/src/App.tsx
git add -A src/howlet/static/app
git commit -m "Frontend: Markets page with Stocks and Crypto tabs"
```

---

### Task 4: Markets page — FX and Economy tabs

**Files:**
- Create: `frontend/src/pages/markets/FxTab.tsx`, `frontend/src/pages/markets/EconomyTab.tsx`
- Modify: `frontend/src/pages/MarketsPage.tsx` (replace the two placeholders)
- Test: `frontend/src/pages/markets/EconomyTab.test.tsx`

**Interfaces:**
- Consumes: `api.fx`, `api.macro`, `api.fedEvents`, `api.regulatory`, types `FxResult`, `MacroResult`, `RegDoc`, `NewsItem` (Task 2); `useApi`; `Block`; `DataTable`; `NewsList`; `fmtNum`.
- Produces:
  - `FxTab()` — `api.fx` refreshed hourly (`3_600_000`; the server caches 1h). Title "FX cross rates · ECB reference, {date} · row → column". Matrix table: header row of `currencies`, first column the row currency, cell `fmtNum(rate, rate >= 100 ? 2 : 4)`, diagonal "—" dim. `!data.matrix` → "FX rates unavailable right now (ECB/Frankfurter unreachable)."
  - `regToNews(d: RegDoc): NewsItem` — `{ title, link: html_url, source: [type ?? "Document", publication_date].filter(Boolean).join(" · "), symbol: null, published: null }` (publication date kept as a raw string in `source`; inventory §8 timezone note).
  - `EconomyTab()` — four independent panels in a 2-column grid:
    1. **Treasury yield curve** (`api.macro`, hourly): `DataTable` maturity / yield (`fmtNum(yield_pct)%`), title includes `date`. If `treasury_yield_curve` is null **or has no `curve` entries** → "Yield curve unavailable right now." (live server returns `{}` today — this must show the message, not crash).
    2. **Jobs & inflation (BLS)** (same `macro` response): rows for `cpi` "CPI (all items)", `unemployment_rate` "Unemployment rate", `nonfarm_payrolls` "Nonfarm payrolls"; each uses `series[0]` — LATEST `value` (raw string, `.num`), PERIOD `` `${period} ${year}` ``; skip empty series; none at all → "BLS series unavailable right now (keyless tier is rate-limited to 25 requests/day/IP)." Below it, when `fred_series` has entries, a "FRED" table (description / latest / date); else if `!fred_available` the hint "Set FRED_API_KEY for deeper macro coverage (GDP, Fed funds rate, mortgage rates…) — free signup at fred.stlouisfed.org." (plain text, no link needed).
    3. **Fed calendar** (`api.fedEvents(20)`, 300 000 ms): `NewsList`, empty "No Fed items right now.".
    4. **SEC rulemaking** (`api.regulatory(15)`, hourly): `NewsList` of `regToNews`, empty "Federal Register unavailable right now.".
  - The macro request failing marks **both** macro panels unavailable (not "Loading…" forever — fixes inventory gotcha 9).

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/markets/EconomyTab.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import EconomyTab, { regToNews } from "./EconomyTab";

afterEach(() => vi.restoreAllMocks());
const json = (b: unknown) => Promise.resolve(new Response(JSON.stringify(b)));

test("regToNews keeps the date-only string raw", () => {
  expect(regToNews({ title: "T", type: "Proposed Rule", document_number: "1", html_url: "https://f/1", publication_date: "2026-10-23" }))
    .toEqual({ title: "T", link: "https://f/1", source: "Proposed Rule · 2026-10-23", symbol: null, published: null });
});

test("empty yield curve shows the unavailable text; BLS renders; panels independent", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const u = String(input);
    if (u.startsWith("/api/macro")) return json({ treasury_yield_curve: {}, fred_available: false, fred_series: {},
      bls_series: { cpi: [{ value: "336.940", period: "September", year: "2026" }], unemployment_rate: [], nonfarm_payrolls: [] } });
    if (u.startsWith("/api/regulatory")) return Promise.resolve(new Response("{}", { status: 502 }));
    return json([]);
  });
  render(<FluentProvider theme={webDarkTheme}><EconomyTab /></FluentProvider>);
  await waitFor(() => expect(screen.getByText("Yield curve unavailable right now.")).toBeTruthy());
  expect(screen.getByText("CPI (all items)")).toBeTruthy();
  expect(screen.getByText("336.940")).toBeTruthy();
  expect(screen.getByText("September 2026")).toBeTruthy();
  expect(screen.getByText(/Set FRED_API_KEY/)).toBeTruthy();
  await waitFor(() => expect(screen.getByText("Unavailable, retrying")).toBeTruthy()); // regulatory only
});
```

- [ ] **Step 2: Run to see it fail** — `npx vitest run src/pages/markets/EconomyTab` — FAIL, module not found.

- [ ] **Step 3: Implement**

`frontend/src/pages/markets/FxTab.tsx`:
```tsx
import { useApi } from "../../lib/useApi";
import { api } from "../../lib/api";
import { fmtNum } from "../../lib/fmt";
import Block from "../../blocks/Block";

const HOUR = 3_600_000;

export default function FxTab() {
  const { data, error, loading, fetchedAt } = useApi("fx", api.fx, HOUR);
  const cur = data?.currencies ?? [];
  return (
    <Block fixed title={`FX cross rates · ECB reference${data?.date ? `, ${data.date}` : ""} · row → column`}
      loading={loading} error={error} fetchedAt={fetchedAt} refreshMs={HOUR}>
      {data && (!data.matrix ? (
        <span style={{ color: "var(--dim)" }}>FX rates unavailable right now (ECB/Frankfurter unreachable).</span>
      ) : (
        <table className="dt">
          <thead><tr><th />{cur.map((c) => <th key={c} style={{ textAlign: "right" }}>{c}</th>)}</tr></thead>
          <tbody>
            {cur.map((row) => (
              <tr key={row}>
                <th style={{ position: "static" }}>{row}</th>
                {cur.map((col) => {
                  const v = data.matrix?.[row]?.[col];
                  return (
                    <td key={col} className="num" style={{ textAlign: "right", color: row === col ? "var(--dim)" : undefined }}>
                      {row === col || v == null ? "—" : fmtNum(v, v >= 100 ? 2 : 4)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      ))}
    </Block>
  );
}
```

`frontend/src/pages/markets/EconomyTab.tsx`:
```tsx
import { useApi } from "../../lib/useApi";
import { api, type NewsItem, type RegDoc } from "../../lib/api";
import { fmtNum } from "../../lib/fmt";
import Block from "../../blocks/Block";
import DataTable from "../../components/DataTable";
import NewsList from "../../components/NewsList";

const HOUR = 3_600_000, FIVE_MIN = 300_000;
const BLS_LABELS: [string, string][] = [["cpi", "CPI (all items)"], ["unemployment_rate", "Unemployment rate"], ["nonfarm_payrolls", "Nonfarm payrolls"]];

export const regToNews = (d: RegDoc): NewsItem => ({
  title: d.title, link: d.html_url,
  source: [d.type ?? "Document", d.publication_date].filter(Boolean).join(" · "),
  symbol: null, published: null,
});

export default function EconomyTab() {
  const macro = useApi("macro", api.macro, HOUR);
  const fed = useApi("fed:20", () => api.fedEvents(20), FIVE_MIN);
  const reg = useApi("reg:15", () => api.regulatory(15), HOUR);
  const m = macro.data;
  const curve = m?.treasury_yield_curve?.curve ?? [];
  const bls = BLS_LABELS.map(([k, label]) => ({ k, label, p: m?.bls_series?.[k]?.[0] })).filter((r) => r.p);
  const fred = Object.entries(m?.fred_series ?? {});
  const box = { height: "calc((100vh - 170px) / 2)" };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))", gap: 12 }}>
      <div style={box}>
        <Block fixed title={`Treasury yield curve${m?.treasury_yield_curve?.date ? ` · ${m.treasury_yield_curve.date}` : ""}`}
          loading={macro.loading} error={macro.error} fetchedAt={macro.fetchedAt} refreshMs={HOUR}>
          {m && (curve.length ? (
            <DataTable columns={[
              { key: "m", label: "Maturity", render: (r) => r.maturity },
              { key: "y", label: "Yield", align: "right", render: (r) => <span className="num">{fmtNum(r.yield_pct)}%</span> },
            ]} rows={curve} rowKey={(r) => r.maturity} empty="Yield curve unavailable right now." />
          ) : <span style={{ color: "var(--dim)" }}>Yield curve unavailable right now.</span>)}
        </Block>
      </div>
      <div style={box}>
        <Block fixed title="Jobs & inflation" loading={macro.loading} error={macro.error} fetchedAt={macro.fetchedAt} refreshMs={HOUR}>
          {m && (
            <>
              {bls.length ? (
                <DataTable columns={[
                  { key: "l", label: "Series", render: (r) => r.label },
                  { key: "v", label: "Latest", align: "right", render: (r) => <span className="num">{r.p!.value}</span> },
                  { key: "p", label: "Period", render: (r) => `${r.p!.period} ${r.p!.year}` },
                ]} rows={bls} rowKey={(r) => r.k} empty="" />
              ) : <div style={{ color: "var(--dim)" }}>BLS series unavailable right now (keyless tier is rate-limited to 25 requests/day/IP).</div>}
              {fred.length > 0 && (
                <>
                  <div style={{ marginTop: 10, fontWeight: 600 }}>FRED (St. Louis Fed)</div>
                  <DataTable columns={[
                    { key: "d", label: "Series", render: ([, v]) => v.description },
                    { key: "l", label: "Latest", align: "right", render: ([, v]) => <span className="num">{v.latest ?? "—"}</span> },
                    { key: "t", label: "Date", render: ([, v]) => v.date ?? "—" },
                  ]} rows={fred} rowKey={([k]) => k} empty="" />
                </>
              )}
              {!fred.length && !m.fred_available && (
                <div style={{ color: "var(--dim)", marginTop: 10 }}>
                  Set FRED_API_KEY for deeper macro coverage (GDP, Fed funds rate, mortgage rates…) — free signup at fred.stlouisfed.org.
                </div>
              )}
            </>
          )}
        </Block>
      </div>
      <div style={box}>
        <Block fixed title="Fed calendar" loading={fed.loading} error={fed.error} fetchedAt={fed.fetchedAt} refreshMs={FIVE_MIN}>
          {fed.data && <NewsList items={fed.data} empty="No Fed items right now." />}
        </Block>
      </div>
      <div style={box}>
        <Block fixed title="SEC rulemaking" loading={reg.loading} error={reg.error} fetchedAt={reg.fetchedAt} refreshMs={HOUR}>
          {reg.data && <NewsList items={reg.data.map(regToNews)} empty="Federal Register unavailable right now." />}
        </Block>
      </div>
    </div>
  );
}
```

In `MarketsPage.tsx` import `FxTab` and `EconomyTab`, replace the two `PlaceholderPage` lines with `<FxTab />` and `<EconomyTab />`, and remove the now-unused `PlaceholderPage` import.

- [ ] **Step 4: Run tests, typecheck, build** — `npx vitest run`, `npx tsc --noEmit`, `npm run build`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/markets frontend/src/pages/MarketsPage.tsx
git add -A src/howlet/static/app
git commit -m "Frontend: Markets FX matrix and Economy tabs"
```

---

### Task 5: Screener page

**Files:**
- Create: `frontend/src/lib/screener.ts`, `frontend/src/pages/ScreenerPage.tsx`
- Modify: `frontend/src/App.tsx` (route `screener`)
- Test: `frontend/src/lib/screener.test.ts`

**Interfaces:**
- Consumes: `api.screener`, `ScreenerRow` (Task 2); `useApi`; `Block`; `DataTable`, `tableCsv`; `downloadCsv`; `Ticker`; `useRoute`; `fmtMoney`, `fmtNum`, `signed`, `tone`.
- Produces:
  - `type ScreenerInputs = { peMax: string; mcapMinB: string; growthMin: string; marginMin: string }`.
  - `buildScreenerQuery(f: ScreenerInputs): { qs: string } | { error: keyof ScreenerInputs }` — blank (after trim) fields are omitted; a non-finite number returns `{ error: field }` (the server would 500 on it — inventory §7); `mcapMinB` is in **billions** and is multiplied by `1e9`; params `pe_ratio_max`, `market_cap_min`, `revenue_growth_pct_min`, `net_margin_pct_min` in that order, via `URLSearchParams`.
  - `ScreenerPage()` — four labelled number inputs (P/E ≤, Market cap ≥ $B, Revenue growth ≥ %, Net margin ≥ %), a **Screen** button; Enter in any input also runs. Never auto-runs on page entry. An invalid field shows Fluent `Field` `validationMessage="Enter a number"` and blocks the run. Running uses `useApi(qs, () => api.screener(qs))` (key = the query string; `null` before the first run; re-running the same query calls `reload()`). Results `Block fixed` title "Results · {matched} of {universe_size} screened", `actions` a **Export CSV** button (`downloadCsv("screener.csv", tableCsv(COLS, rows))`). Columns: Symbol (`Ticker`), Price, %Chg (signed, toned), Mkt cap (`fmtMoney`), P/E (1dp), Revenue (`fmtMoney`), Rev growth (signed %, toned), Net margin (1dp %). Row click opens the stock page. Loading text "Screening (first run per day is slow — same-day results are cached)…"; empty "No matches out of {universe_size} screened."; errors show the server text (SEC fundamentals → `sec` Block).

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/screener.test.ts`:
```ts
import { buildScreenerQuery } from "./screener";

const empty = { peMax: "", mcapMinB: "", growthMin: "", marginMin: "" };

test("blank fields are omitted; market cap is in billions", () => {
  expect(buildScreenerQuery(empty)).toEqual({ qs: "" });
  expect(buildScreenerQuery({ ...empty, peMax: " 15 ", mcapMinB: "2.5" }))
    .toEqual({ qs: "pe_ratio_max=15&market_cap_min=2500000000" });
  expect(buildScreenerQuery({ peMax: "20", mcapMinB: "", growthMin: "-5", marginMin: "10" }))
    .toEqual({ qs: "pe_ratio_max=20&revenue_growth_pct_min=-5&net_margin_pct_min=10" });
});

test("non-numeric input names the bad field", () => {
  expect(buildScreenerQuery({ ...empty, growthMin: "abc" })).toEqual({ error: "growthMin" });
  expect(buildScreenerQuery({ ...empty, peMax: "1e999" })).toEqual({ error: "peMax" });
});
```

- [ ] **Step 2: Run to see it fail** — `npx vitest run src/lib/screener` — FAIL.

- [ ] **Step 3: Implement**

`frontend/src/lib/screener.ts`:
```ts
export type ScreenerInputs = { peMax: string; mcapMinB: string; growthMin: string; marginMin: string };

const FIELDS: [keyof ScreenerInputs, string, number][] = [
  ["peMax", "pe_ratio_max", 1],
  ["mcapMinB", "market_cap_min", 1e9],
  ["growthMin", "revenue_growth_pct_min", 1],
  ["marginMin", "net_margin_pct_min", 1],
];

export function buildScreenerQuery(f: ScreenerInputs): { qs: string } | { error: keyof ScreenerInputs } {
  const p = new URLSearchParams();
  for (const [field, param, scale] of FIELDS) {
    const raw = f[field].trim();
    if (!raw) continue;
    const n = Number(raw);
    if (!Number.isFinite(n)) return { error: field };
    p.set(param, String(n * scale));
  }
  return { qs: p.toString() };
}
```

`frontend/src/pages/ScreenerPage.tsx`:
```tsx
import { Button, Field, Input } from "@fluentui/react-components";
import { useState } from "react";
import { useApi } from "../lib/useApi";
import { api, type ScreenerRow } from "../lib/api";
import { buildScreenerQuery, type ScreenerInputs } from "../lib/screener";
import { fmtMoney, fmtNum, signed, tone } from "../lib/fmt";
import { downloadCsv } from "../lib/csv";
import { useRoute } from "../lib/route";
import Block from "../blocks/Block";
import DataTable, { tableCsv, type Column } from "../components/DataTable";
import Ticker from "../components/Ticker";

const pct = (n: number | null) => <span className="num" style={{ color: tone(n) }}>{n == null ? "—" : `${signed(n, 1)}%`}</span>;

const COLS: Column<ScreenerRow>[] = [
  { key: "s", label: "Symbol", render: (r) => <Ticker symbol={r.symbol} />, csv: (r) => r.symbol },
  { key: "p", label: "Price", align: "right", render: (r) => <span className="num">{fmtNum(r.price)}</span>, csv: (r) => r.price },
  { key: "c", label: "%Chg", align: "right", render: (r) => pct(r.change_pct), csv: (r) => r.change_pct },
  { key: "m", label: "Mkt cap", align: "right", render: (r) => <span className="num">{fmtMoney(r.market_cap)}</span>, csv: (r) => r.market_cap },
  { key: "pe", label: "P/E", align: "right", render: (r) => <span className="num">{fmtNum(r.pe_ratio, 1)}</span>, csv: (r) => r.pe_ratio },
  { key: "rev", label: "Revenue", align: "right", render: (r) => <span className="num">{fmtMoney(r.revenue)}</span>, csv: (r) => r.revenue },
  { key: "g", label: "Rev growth", align: "right", render: (r) => pct(r.revenue_growth_pct), csv: (r) => r.revenue_growth_pct },
  { key: "nm", label: "Net margin", align: "right", render: (r) => <span className="num">{r.net_margin_pct == null ? "—" : `${fmtNum(r.net_margin_pct, 1)}%`}</span>, csv: (r) => r.net_margin_pct },
];

const LABELS: [keyof ScreenerInputs, string][] = [
  ["peMax", "P/E ≤"], ["mcapMinB", "Market cap ≥ ($B)"], ["growthMin", "Revenue growth ≥ (%)"], ["marginMin", "Net margin ≥ (%)"],
];

export default function ScreenerPage() {
  const [inputs, setInputs] = useState<ScreenerInputs>({ peMax: "", mcapMinB: "", growthMin: "", marginMin: "" });
  const [bad, setBad] = useState<keyof ScreenerInputs | null>(null);
  const [qs, setQs] = useState<string | null>(null);
  const go = useRoute((r) => r.go);
  const res = useApi(qs, () => api.screener(qs ?? ""));

  const run = () => {
    const q = buildScreenerQuery(inputs);
    if ("error" in q) { setBad(q.error); return; }
    setBad(null);
    if (q.qs === qs) res.reload(); else setQs(q.qs);
  };

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
        {LABELS.map(([k, label]) => (
          <Field key={k} label={label} validationMessage={bad === k ? "Enter a number" : undefined} validationState={bad === k ? "error" : "none"}>
            <Input value={inputs[k]} inputMode="decimal" style={{ width: 150 }}
              onChange={(_, d) => setInputs({ ...inputs, [k]: d.value })}
              onKeyDown={(e) => { if (e.key === "Enter") run(); }} />
          </Field>
        ))}
        <Button appearance="primary" onClick={run}>Screen</Button>
      </div>
      {qs !== null && (
        <div style={{ height: "calc(100vh - 210px)" }}>
          <Block fixed sec title={res.data ? `Results · ${res.data.matched} of ${res.data.universe_size} screened` : "Results"}
            loading={res.loading} error={res.error} fetchedAt={res.fetchedAt}
            actions={res.data?.rows.length ? <Button size="small" onClick={() => downloadCsv("screener.csv", tableCsv(COLS, res.data!.rows))}>Export CSV</Button> : undefined}>
            {!res.data && !res.error && <span style={{ color: "var(--dim)" }}>Screening (first run per day is slow — same-day results are cached)…</span>}
            {res.data && <DataTable columns={COLS} rows={res.data.rows} rowKey={(r) => r.symbol}
              empty={`No matches out of ${res.data.universe_size} screened.`}
              onRowClick={(r) => go({ kind: "stock", symbol: r.symbol, tab: "overview" })} />}
          </Block>
        </div>
      )}
    </div>
  );
}
```

In `App.tsx` add `import ScreenerPage from "./pages/ScreenerPage";` and render it when `route.page === "screener"`.

- [ ] **Step 4: Run tests, typecheck, build** — `npx vitest run`, `npx tsc --noEmit`, `npm run build`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/screener.ts frontend/src/lib/screener.test.ts frontend/src/pages/ScreenerPage.tsx frontend/src/App.tsx
git add -A src/howlet/static/app
git commit -m "Frontend: Screener page with validation and CSV export"
```

---

### Task 6: Carry-overs, docs and live pass

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx` (grid `measureBeforeMount`), `frontend/src/main.tsx` (apply theme CSS vars before first render), `frontend/src/blocks/WatchlistBlock.tsx` (empty list message), `CLAUDE.md` (Status line)
- Test: `frontend/src/blocks/WatchlistBlock.test.tsx`

**Interfaces:**
- Consumes: `applyCssVars`, `resolveMode` (`theme/theme.ts`); `useSettings`; `getWatchlists`.
- Produces: no new exports.

Carry-overs from `docs/superpowers/plans/2026-10-23-react-shell-followups.md`:
1. Home grid width flash → add `measureBeforeMount` to the `<Grid …>` props in `HomePage.tsx`.
2. Possible white flash in dark mode → in `main.tsx`, before `createRoot(...)`, call:
```ts
import { applyCssVars, resolveMode } from "./theme/theme";
import { useSettings } from "./lib/settings";
const s0 = useSettings.getState().settings;
applyCssVars(resolveMode(s0.themeMode, window.matchMedia("(prefers-color-scheme: dark)").matches) === "dark", s0.accent);
```
3. Empty/unknown watchlist → `WatchlistBlock` must not call `/api/quotes` with no symbols; when the list is empty or missing it renders "Empty list — add symbols in the classic view's MY screen for now." (the add-symbol UI arrives with the Portfolio page in 2c). Implement by passing `null` as the `useApi` key when `symbols.length === 0`.

- [ ] **Step 1: Write the failing test**

`frontend/src/blocks/WatchlistBlock.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import WatchlistBlock from "./WatchlistBlock";

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

test("an empty list shows a hint and makes no request", () => {
  localStorage.setItem("howlet_watchlists_v1", JSON.stringify({ default: ["AAPL"], empty: [] }));
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  render(<FluentProvider theme={webDarkTheme}><WatchlistBlock list="empty" /></FluentProvider>);
  expect(screen.getByText(/Empty list/)).toBeTruthy();
  expect(fetchSpy).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run to see it fail** — `npx vitest run src/blocks/WatchlistBlock` — FAIL (it fetches and shows no hint).

- [ ] **Step 3: Implement the three carry-overs** as described above. In `WatchlistBlock.tsx` change the `useApi` call's key to `symbols.length ? \`wl:${list}:${symbols.join(",")}\` : null` and render, inside the `Block`, `{!symbols.length && <span style={{ color: "var(--dim)" }}>Empty list — add symbols in the classic view's MY screen for now.</span>}`.

- [ ] **Step 4: CLAUDE.md** — under "## Status", update the React-shell status line (added 2026-10-23) to also list "News, Markets (stocks/crypto/FX/economy) and Screener pages (2026-10-24)". Change nothing else.

- [ ] **Step 5: Run everything** — `npx vitest run`, `npx tsc --noEmit`, `npm run build`; from repo root `PYTHONPATH=src pytest tests/ -q` and `ruff check src/ tests/`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/HomePage.tsx frontend/src/main.tsx frontend/src/blocks/WatchlistBlock.tsx frontend/src/blocks/WatchlistBlock.test.tsx CLAUDE.md
git add -A src/howlet/static/app
git commit -m "Frontend: grid measure-before-mount, early theme vars, empty watchlist hint"
```

- [ ] **Step 7: Live pass (controller)** at `http://localhost:8813/`:
  1. News: three panels fill; links open in a new tab; Fed panel independent.
  2. Markets → Stocks (5 sections, sparklines, ticker click opens stock page), Crypto (source label, $ digits for sub-$1 coins), FX (9×9 matrix, diagonal "—"), Economy (yield curve shows "unavailable" today — see adjacent-issue note; BLS rows; FRED hint; Fed calendar; SEC rulemaking with raw dates). Tab choice survives reload.
  3. Screener: `abc` in a field shows "Enter a number" and sends nothing; P/E ≤ 15 returns rows; Export CSV downloads; row click opens the stock page.
  4. Home: no horizontal scrollbar on load; reload in dark mode shows no white flash.
  5. Console clean.

## Adjacent issue (not in scope — flag to Vineeth)
`/api/macro` returns `treasury_yield_curve: {}` live on 2026-10-24, so the yield curve is unavailable in **both** UIs. The Treasury feed or its parser (`macro.py`) needs a look — CLAUDE.md records a past namespace bug in exactly this parser.
