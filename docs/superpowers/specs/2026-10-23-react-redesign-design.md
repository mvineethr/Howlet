# Howlet React redesign: design

Date: 2026-10-23. Status: approved in brainstorming, awaiting spec review.
Sub-project 1 of 4. The paper account, Schwab Trader API and Laya each get
their own spec later.

## Goal

Replace the single-file vanilla-JS dashboard (`src/howlet/dashboard.html`,
2,641 lines, 96 functions) with a React app that:

- does not feel overwhelming: few blocks by default, and designed pages
  instead of free-form clutter;
- feels native on Windows 11: Fluent UI, Segoe UI, follows the Windows
  light/dark setting;
- can be customized four ways: blocks and layout, look, rail pages, and
  defaults and behavior;
- has a Howlet twist: 🦉 chips showing which tracked superinvestors hold a
  stock.

The chosen direction is mockup **A, "Calm Fluent"**: a slim left rail like
Windows Settings, roomy cards, and 3 to 4 blocks on first run.

## Non-goals

- No change to the Python side. `views.py`, the 28 Flask routes, the MCP
  server (27 tools) and the CLI stay untouched, except for serving the
  new build and moving the old page to `/classic`.
- No new data sources, and no paper trading, Schwab or Laya. The Portfolio
  page only reserves an account switcher for them.
- No mobile layout. The audience is desktop; the existing deferral stands.

## Architecture

- **Location:** `frontend/` at the repo root. It contains React 18,
  TypeScript, Vite and Fluent UI React v9 (`@fluentui/react-components`,
  MIT).
- **Build output:** `npm run build` writes to `src/howlet/static/app/`.
  Flask serves `static/app/index.html` at `/`. The built files are
  committed, so `howlet dashboard` runs without Node. Node is needed only
  to change the UI.
- **Dev loop:** `npm run dev` runs the Vite dev server with `/api`
  proxied to Flask on port 8813.
- **Old UI:** today's `dashboard.html` is served at `/classic` until
  every feature is ported and verified, then deleted.
- **Libraries:**
  - `klinecharts` from npm, the same Apache-2.0 library as today. Its
    theme still reads the colour tokens.
  - `react-grid-layout` (MIT) for drag-and-resize on Home.
  - `zustand` for small stores. No Redux, no router library: the rail
    page is state, and a URL hash (`#/stock/AAPL`) keeps BACK working.
- **Fonts:** Segoe UI Variable / Segoe UI for text, and Cascadia Mono /
  Consolas with tabular figures for numbers. These are system fonts, with
  no web-font download.
- **Repo hygiene:** add `frontend/node_modules/` and `.superpowers/` to
  `.gitignore`. Add `static/app/**` to package data so a built wheel would
  include it.

## Theme and tokens

- One token set in `frontend/src/theme/tokens.ts` is the single source of
  every colour. This carries the CLAUDE.md rule that "colour lives in
  `:root` only" into the new app.
- The Fluent theme is generated from it with `createDarkTheme` /
  `createLightTheme` and a brand ramp built on amber `#eaa53e`, hue 36.
- Tokens are also written to CSS variables, so KLineChart and any
  plain CSS read the same values. No hex literals outside `tokens.ts`.
- Theme mode can be System (the default, via `prefers-color-scheme`),
  Light or Dark. Accent is user-pickable, with amber as the default.

## Pages (the rail)

The rail order is the default; users can reorder and hide pages in
Settings.

| Rail page | Contents (ported from) |
|---|---|
| 🏠 Home | Block grid with drag/resize and extra user tabs. First run shows Watchlist, Smart money moves, Market pulse and News. |
| 📈 Markets | Sub-tabs: Stocks/Crypto (MKTS), FX matrix, Economy (ECO: Treasury, BLS, FRED, Fed, SEC rulemaking) |
| 🦉 Smart Money | Managers (PORT + Q/Q diff), Consensus, Insider buys, Position history, Filing search (full text), Funds (N-PORT) |
| 🔍 Screener | EQS |
| 📰 News | The 7 feeds (NEWS) |
| 💼 Portfolio | Holdings (MY) + Risk (PF). There is an account switcher with one entry, "Manual holdings", for now. |
| ⚙ Settings | See below |

The **stock page** has no rail item. Any ticker click, or search,
opens `#/stock/SYM` with these tabs: Overview (quote, key stats, 🦉
chips), Chart (KLineChart, indicators, drawing, ORB), Financials (FA),
Holders (13F holders + Form 4 insiders + filings feed), News, and
Options. Options is hidden unless enabled in Settings, because it is
experimental.

**🦉 chips:** on the stock Overview and in watchlist rows, the chips list
the tracked managers holding the symbol and their last-quarter action
(new, added, trimmed, exited), from `/api/holders/<symbol>`. If that call
fails, no chip is shown and no error appears, because it is decoration.

**Blocks:** Home can hold every block type that exists today (17), each
a self-contained component with its own data hook.

## Command box (Ctrl+K)

- It opens from anywhere and fuzzy-matches tickers, managers (the 14
  presets + CIK), pages and commands.
- These classic commands keep working: `AAPL DES|FA|HDS|GP|OPT`,
  `buffett` / `<CIK>` / `X PORT`, `HOME`, `MKTS`, `NEWS`, `ECO`, `EQS`,
  `PF`, `HELP`, and `ALERT SYM >|< PRICE`.
- Shortcuts: Ctrl+1 to Ctrl+7 switch rail pages, and Esc closes overlays.
  A shortcut list appears in Settings and in the box's footer.

## Settings

- **Appearance:** theme mode, accent colour, density (comfortable /
  compact), text size (small / medium / large).
- **Rail:** show, hide and reorder pages. Home and Settings cannot be
  hidden.
- **Defaults:** start page, default chart range, default indicators,
  refresh speed (fast 15s / normal 60s / slow 5m), alert sound on/off,
  tracked managers (the presets plus custom CIKs), and show Options.
- **Layouts:** named layout snapshots, restore the default layout, and
  EXPORT/IMPORT of all `howlet_*` state as a JSON backup.

All settings live under one localStorage key, `howlet_settings_v1`,
with schema version and defaults merged on load.

## Data flow

- `frontend/src/api.ts` is one typed wrapper over `fetch` for every
  `/api/*` route. It throws on non-2xx and reads the JSON error body
  that Flask already returns (`RequestException` maps to 502 JSON).
- `useApi(key, fetcher, {refreshMs})` is a small hook that gives each
  block its own loading, error, data and refresh timer. Blocks never
  share a global refresh, so one slow source cannot freeze the page.
  The "refresh speed" setting applies to market, news and crypto blocks
  only. SEC-backed blocks keep their own slow cadence (filing alerts stay
  at 30 minutes), because filings are immutable and SEC is throttled.
- Prices update in place. A changed value flashes up or down briefly,
  and this is off under `prefers-reduced-motion`.
- Stale data, meaning a quote older than 2× the refresh interval, shows
  "as of HH:MM" instead of posing as live.

## Existing user data (migration)

The new app reads the existing keys unchanged: `howlet_layout_v1`,
`howlet_layouts_v1`, `howlet_watchlists_v1` (and legacy
`howlet_watchlist`), `howlet_pf_holdings`, `howlet_price_alerts_v1`,
`howlet_seen_filings_v1`, `howlet_mkts_mode`.

The old layout format, a list of widget types per tab with wide/tall
flags, converts once into react-grid-layout positions on first load. The
original key is left untouched, so `/classic` keeps working during the
port.

## Errors

- A failing endpoint affects only its own block, which shows a quiet
  "Unavailable, retrying" with a retry button. The page keeps working.
- SEC-backed blocks may show real error text. Market, news and crypto
  blocks degrade silently, which matches the "SEC is authoritative,
  market data is decoration" rule.
- A malformed localStorage value falls back to defaults and never white-
  screens. A top-level error boundary offers "Reset settings" and leaves
  watchlists and portfolio alone.

## Testing

- **Vitest:** the command parser, alert rule evaluation, settings
  load/merge, the old-layout to grid-layout migration, and the token to
  Fluent-theme mapping.
- **Python:** the 150 existing tests stay green, plus one route test that
  `/` serves the built app and `/classic` serves the old page.
- **Live:** each ported page is checked in the browser against the real
  APIs before it counts as done. This includes checking computed styles
  for fonts and colours, per the CLAUDE.md gotchas.

## Done means

Every feature reachable in `/classic` is reachable in the new UI and
verified live. Then `/classic` and `dashboard.html` are deleted and
CLAUDE.md is updated.

## Risks

- **Size:** this is the largest single job on the list. The work is
  ordered as shell first (rail, theme, settings, command box), then
  pages, with a checkpoint after the shell.
- **Node toolchain:** adds a Node/npm dependency to change the UI. The
  runtime still needs only Python.
- **Fluent UI v9 bundle size:** expected around 300 to 500 KB gzipped. It
  is acceptable for a local app, but it gets measured at the first build.
