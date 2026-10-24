# React shell: carry-overs for plan 2

These are findings from the per-task reviews and the final review of plan 1
(`2026-10-23-react-shell.md`). Each was triaged as "plan 2", not "must fix now".
Plan 2 ports the remaining pages and deletes `/classic`.

## Visible to the user
- **Home grid width:** react-grid-layout's `WidthProvider` starts at a default
  width and measures late (seen in a background pane), which shows a horizontal
  scrollbar until it re-measures. Fix: `measureBeforeMount` on the grid.
- **Owl chips appear slowly:** `/api/holders` takes about 2 minutes cold and
  about 38 seconds warm, because it resolves CUSIPs for all 14 managers. Add a
  loading hint, and speed up the backend (for example, cache the resolved
  ticker-to-holders map per quarter).
- **Chip actions:** the spec wants last-quarter action (new, added, trimmed,
  exited) on the chips. `/api/holders` doesn't return it yet, so it needs a
  backend change.
- **Bell popover:** clips past the right edge at about 800px wide.
- **Ctrl+1..7:** works in the preview pane but is unverified in a real
  Edge/Chrome window, where Ctrl+digit may switch browser tabs. It also
  indexes the rail in a different order from what's drawn if Settings is
  moved up the rail.
- **Empty or unknown watchlist:** shows "Unavailable, retrying" instead of
  "Empty list".
- **Possible white flash in dark mode:** the CSS variables are set in an
  effect after first paint. Call `applyCssVars` before render in `main.tsx`.

## Robustness
- `useApi`: the spinner shows on every refresh; `loading` can stick if the key
  becomes `null` mid-request; the `catch` assumes an `Error`.
- `mergeSettings` returns default arrays by reference (`railOrder === PAGE_IDS`).
- Settings import: a storage-write failure shows "not a Howlet backup"; the
  colour picker writes settings on every drag tick; the export object URL is
  never revoked.
- `chime()` creates an `AudioContext` per alert and never closes it.
- `buffett` routes to the stock page `BUFFETT` if `/api/managers` hasn't
  loaded.
- `HomePage.addBlock` writes `y: Infinity`, which serialises to `null`.
- The error boundary's Reset can throw if storage is blocked.
- `/classic?cmd=` runs any command from the URL. This is acceptable on
  localhost.
- `news.py` should drop non-http(s) links server-side. The frontend already
  guards them.

## Tests and tooling
- Missing tests: `Block` error and stale branches, `Num` formatting,
  `useRoute.go` and `hashchange`, `useApi` HTTP fallback and interval, theme
  light-mode branch and SURFACES, the `/` fallback route, and more Settings
  cases.
- The OwlChips failure test uses a fixed 20ms wait.
- Stale comment in `tests/test_smoke.py` ("/ reads only the HTML file").
- `npm audit` warnings are not triaged (dev toolchain only).
- Bundle: 765 kB raw, 220 kB gzipped. Vite warns that the chunk is over
  500 kB. Code-split per page when plan 2 adds pages.

## Added by plan 2a (2026-10-24)
Resolved in 2a: Home grid width flash (ResizeObserver-measured grid), dark-mode white flash (CSS vars before render),
empty-watchlist request.
Still open:
- DataTable: clickable rows aren't keyboard-reachable; `tableCsv` silently blanks columns without a `csv` accessor.
- Page heights hard-code chrome height (`calc(100vh - N)`); `App.tsx` page switch is a 5-deep ternary — use a map in 2b.
- Crypto: "top 0" title when empty; table overflows narrow widths. StocksTab renders empty tables for empty sections.
- FxTab: `{matrix: {}}` would render an empty table (fx.py degrades the whole response today, so not hit); no FxTab test.
- No HomePage unit test (jsdom `clientWidth` is 0 and gates the grid).
- `useApi` starts a new request each interval even if the previous one is still in flight.
- **Backend:** `/api/macro` returns `treasury_yield_curve: {}` live (2026-10-24) — yield curve unavailable in both UIs.

## Added by plan 2b (2026-10-24)
Resolved in 2b: options expiry leaking across symbols, insider row-key collisions, chart theme race, "retrying" text on
non-polling panels, financials CSV end_date.
Still open:
- Chart: a range change disposes/re-creates the chart (drawings lost, brief flash); range never saved to
  `settings.chartRange`; default indicators are `["MA"]` (classic showed MA + VOL + MACD).
- Overview: studies/range-change always use the 6mo range; absolute 1-day change not shown; Quote/Studies blank while
  the quote loads; Chart tab issues a duplicate `/api/security` at 6mo (header + chart).
- Options: expiry dropdown unmounts while a new chain loads (useApi clears data on key change).
- Financials `money()` uses a loose `keyof` cast. FinancialsTab test overwrites `URL.createObjectURL` without restoring.
- Tests missing: memo TTL expiry, ORB badge branch, populated holders table, options expiry change.
- Backend: a cold `/api/holders` (OwlChips fires it on every stock visit) holds `edgar_lock` and queues events/insiders/
  filings behind it on first visit — CLAUDE.md Next-features item 4.
- CLAUDE.md KLineChart gotcha line reads awkwardly after the 2b edit.
