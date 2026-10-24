# Howlet React pages 2d: blocks, Home tabs, Help, tracked managers, retire /classic — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the redesign: all 17 classic Home block types (plus Market pulse) on the React Home grid, Home tabs (create/rename/delete) and named layout snapshots, a Help page, the two spec features that need the backend (🦉 chip last-quarter actions; user-chosen tracked managers), and finally delete the classic UI.

**Architecture:** Part 4 of 4 of plan 2. Blocks reuse the page panels instead of duplicating them: each panel component takes an optional `onRemove` — with it, the panel renders as a draggable, removable Home block; without it, as a fixed page panel. Backend changes are additive (optional parameters / extra fields), so the MCP server and CLI keep working unchanged. The last task deletes `dashboard.html` and `/classic` only after everything is ported. Classic reference: `docs/superpowers/plans/classic-inventory.md` (§10 HELP, §11 HOME, widget table).

**Tech Stack:** React 18, TypeScript, Vite 5, Fluent UI v9, zustand, Vitest; Python 3 / Flask / pytest for Task 5.

## Global Constraints

- Colour hex literals only in `frontend/src/theme/tokens.ts`; numbers use `.num`; up/down via `tone()` / CSS variables.
- Date-only strings shown raw; external links only via `safeHref` with `rel="noopener noreferrer"`.
- SEC-backed panels use `Block sec`; market/news panels degrade quietly; panels load independently.
- No SEC panel polls faster than classic did (classic widgets: insiders and filings 300 s; everything else SEC-backed never polls). World markets ≥ 300 s; crypto ≥ 120 s.
- Shared keys keep their classic shapes while `/classic` exists (Tasks 1–5). New React-only state lives in new keys: `howlet_home_v1` (exists), `howlet_home_snapshots_v1` (new).
- Backend changes (Task 5 only) are additive: every new parameter is optional with today's behaviour as the default; existing JSON fields keep their names/types; `views.py` stays the single source for Flask and MCP. Keep SEC self-throttle and the "no required API key" rule.
- Run frontend commands from `frontend/`; build with `npm run build` and commit `src/howlet/static/app` (stage with `git add -A src/howlet/static/app`) in every task that changes UI. Python: from repo root `PYTHONPATH=src pytest tests/ -q` and `ruff check src/ tests/`. Verify live at `http://localhost:8813/`.

## File structure

```
frontend/src/
  lib/events.ts                     # useSequentialEvents (extracted from WatchlistsTab)
  lib/homeState.ts                  # pure Home tab + snapshot ops
  blocks/registry.tsx               # 18 block types with `needs` + defaultConfig
  blocks/AddBlockDialog.tsx         # pick type + config (manager / list / symbol)
  blocks/WorldMarketsBlock.tsx      # compact markets (no sparklines)
  pages/smart/panels.tsx            # HoldingsPanel, ConsensusPanel, PositionHistoryPanel, InsiderBuysPanel, FundPanel
  pages/stock/panels.tsx            # InsidersPanel, FilingsPanel
  pages/markets/panels.tsx          # YieldCurvePanel, FedPanel
  pages/HelpPage.tsx                # routed as #/settings/help
  pages/HomePage.tsx                # tabs, snapshots, AddBlockDialog
src/howlet/views.py, dashboard.py   # Task 5: managers param, holder actions
src/howlet/dashboard.html           # deleted in Task 6
```

---

### Task 1: Embeddable panels (refactor, no behaviour change)

**Files:**
- Create: `frontend/src/lib/events.ts`, `frontend/src/pages/smart/panels.tsx`, `frontend/src/pages/stock/panels.tsx`, `frontend/src/pages/markets/panels.tsx`
- Modify: `frontend/src/pages/smart/ManagersTab.tsx`, `ConsensusTab.tsx`, `PositionHistoryTab.tsx`, `InsiderBuysTab.tsx`, `FundsTab.tsx`; `frontend/src/pages/stock/HoldersTab.tsx`; `frontend/src/pages/markets/EconomyTab.tsx`, `CryptoTab.tsx`, `FxTab.tsx`; `frontend/src/pages/portfolio/WatchlistsTab.tsx`
- Test: `frontend/src/pages/panels.test.tsx`

**Interfaces:**
- Every panel below has the shape `(props: {...; onRemove?: () => void}) => JSX.Element` and renders exactly one `Block` with `fixed={!onRemove}` and `onRemove={onRemove}` passed through (so on a page it is fixed; on Home it is draggable with a ✕). Their content, keys, refresh intervals, empty texts and `sec` flags are moved **unchanged** from where they live today:
  - `pages/smart/panels.tsx`: `HoldingsPanel({ manager, top = 25, compact = false })` (ManagersTab's Holdings block; `compact` drops the Price, 1M and Shares columns — classic widget 1 shape — and the CSV button); `ConsensusPanel({ min = 2, limit = 25 })` (ConsensusTab's Block; the min dropdown stays in ConsensusTab); `PositionHistoryPanel({ manager, query })` (the Block part of PositionHistoryTab); `InsiderBuysPanel({ list })` (InsiderBuysTab's Block incl. the no-symbols hint; the list dropdown stays in the tab); `FundPanel({ symbol, top = 50 })` (FundsTab's Block).
  - `pages/stock/panels.tsx`: `InsidersPanel({ symbol })`, `FilingsPanel({ symbol })` (HoldersTab's 2nd and 3rd blocks).
  - `pages/markets/panels.tsx`: `YieldCurvePanel()` (EconomyTab's yield-curve block incl. its loading text), `FedPanel({ limit = 20 })` (EconomyTab's Fed calendar block).
  - `CryptoTab` and `FxTab` gain `onRemove?` (and `CryptoTab` a `limit = 50` prop) the same way.
- `lib/events.ts`: `useSequentialEvents(symbols: string[]): Map<string, Events | "error">` — the module-level cache + one-at-a-time loader currently inside `WatchlistsTab.tsx`, moved verbatim (returns the cache snapshot; re-renders after each symbol). `WatchlistsTab` uses it.
- The tabs then render these panels; their visible behaviour must not change.

- [ ] **Step 1: Write the failing test** — `frontend/src/pages/panels.test.tsx`:
```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { FluentProvider, webDarkTheme } from "@fluentui/react-components";
import { FedPanel } from "./markets/panels";

afterEach(() => vi.restoreAllMocks());

test("a panel with onRemove shows a remove button and calls it; without, none", () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]"));
  const onRemove = vi.fn();
  const { unmount } = render(<FluentProvider theme={webDarkTheme}><FedPanel limit={10} onRemove={onRemove} /></FluentProvider>);
  fireEvent.click(screen.getByRole("button", { name: /Remove/ }));
  expect(onRemove).toHaveBeenCalled();
  unmount();
  render(<FluentProvider theme={webDarkTheme}><FedPanel limit={10} /></FluentProvider>);
  expect(screen.queryByRole("button", { name: /Remove/ })).toBeNull();
});
```
- [ ] **Step 2: Run to see it fail.**
- [ ] **Step 3: Extract** the panels and hook as listed. Keep every existing test green without editing its assertions (they are the refactor's safety net); only adjust imports if a test imported a moved symbol.
- [ ] **Step 4:** `npx vitest run`, `npx tsc --noEmit`, `npm run build`.
- [ ] **Step 5: Commit** — `git add frontend/src && git add -A src/howlet/static/app && git commit -m "Frontend: embeddable panels (page or Home block) and shared events loader"`.

---

### Task 2: All Home block types and the Add-block dialog

**Files:**
- Create: `frontend/src/blocks/AddBlockDialog.tsx`, `frontend/src/blocks/WorldMarketsBlock.tsx`
- Modify: `frontend/src/blocks/registry.tsx`, `frontend/src/pages/HomePage.tsx`
- Test: `frontend/src/blocks/registry.test.ts` (extend), `frontend/src/blocks/AddBlockDialog.test.tsx`

**Interfaces:**
- `registry.tsx`: `type Needs = "manager" | "list" | "symbol" | "manager-symbol" | null`; `type Entry = { label: string; needs: Needs; defaultSize: {w,h}; render: (cfg, onRemove) => JSX.Element }`; `BLOCKS` gains (classic key names kept so migrated classic layouts render): `manager-portfolio` "13F portfolio" (manager; `HoldingsPanel compact top=15`), `consensus` "Smart money consensus" (null; `ConsensusPanel limit=10`), `watchlist-news` "Watchlist news" (list; `NewsList` of `api.newsFor(stockSymbols(list).slice(0,10), 20)` every 300 s, empty "No headlines yet for these names."), `watchlist-events` "Watchlist events" (list; `useSequentialEvents(stockSymbols(list).slice(0,8))`, columns Symbol / Next earnings / Analysts), `insiders` "Insider transactions" (symbol; `InsidersPanel`), `insider-buys` "Insider buys (screen)" (list; `InsiderBuysPanel`), `position-history` "13F position history" (manager-symbol; `PositionHistoryPanel`), `fed` "Fed & policy" (null; `FedPanel limit=10`), `yield-curve` "Treasury yield curve" (null; `YieldCurvePanel`), `world-markets` "World markets" (null; `WorldMarketsBlock`, default w 12), `crypto` "Crypto top 20" (null; `CryptoTab limit=20`), `filings` "SEC filings" (symbol; `FilingsPanel`), `fx-matrix` "FX cross rates" (null; `FxTab`), `fund` "ETF/fund holdings" (symbol; `FundPanel top=25`). Existing four keep their keys and get `needs` (`watchlist`: list, `manager-changes`: manager, `pulse`/`market-news`: null). Titles show the config (e.g. "13F portfolio · buffett", "SEC filings · AAPL") — panels already include the subject in their titles; where they don't, pass it.
- `WorldMarketsBlock({ onRemove })` — one Block; `api.markets` at `Math.max(REFRESH_MS[refresh], 300_000)`; sections side by side (flex-wrap, min 240 px): section title + rows Ticker / label (dim) / price / %chg (no sparklines).
- `blockFor(type)` fallback (unknown types) now reads "Unknown block type — remove it." (no `/classic` link).
- `AddBlockDialog({ open, onClose, onAdd: (type: string, config: Record<string,string>) => void })` — Fluent `Dialog`: a block-type `Dropdown` (labels), then fields by `needs`: manager → `ManagerPicker`; list → `Dropdown` of `getWatchlists()` names; symbol → `Input` (upper-cased); manager-symbol → both. **Add** is disabled until required fields are filled; config keys are `manager`, `list`, `symbol`.
- `HomePage`: the "Add block" menu is replaced by a button opening `AddBlockDialog`; `addBlock(type, config)` places the block with the type's `defaultSize`.

- [ ] **Step 1: Failing tests** — extend `registry.test.ts`:
```ts
test("every classic widget type is registered with its needs", () => {
  const classic = ["manager-portfolio", "manager-changes", "consensus", "watchlist", "watchlist-news", "watchlist-events",
    "insiders", "insider-buys", "position-history", "market-news", "fed", "yield-curve", "world-markets", "crypto",
    "filings", "fx-matrix", "fund"];
  for (const t of classic) expect(BLOCKS[t], t).toBeDefined();
  expect(BLOCKS["position-history"].needs).toBe("manager-symbol");
  expect(BLOCKS.fund.needs).toBe("symbol");
  expect(BLOCKS.pulse.needs).toBeNull();
});
```
and `AddBlockDialog.test.tsx`: open the dialog, pick "SEC filings", type `aapl`, click Add → `onAdd` called with `("filings", { symbol: "AAPL" })`; with an empty symbol Add is disabled. (Mock `/api/managers` with `[]`.)
- [ ] **Step 2: Run to see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** `npx vitest run`, `npx tsc --noEmit`, `npm run build`.
- [ ] **Step 5: Commit** — registry, dialog, WorldMarketsBlock, HomePage, tests, bundle: `"Frontend: all Home block types with an add-block dialog"`.

---

### Task 3: Home tabs and saved layouts

**Files:**
- Create: `frontend/src/lib/homeState.ts`
- Modify: `frontend/src/pages/HomePage.tsx`, `frontend/src/pages/SettingsPage.tsx` (the "Restore default Home" button uses `homeState`)
- Test: `frontend/src/lib/homeState.test.ts`

**Interfaces:**
- `homeState.ts` (pure, never mutates input; `HomeState`/`HomeTab` from `lib/legacy.ts`): `addTab(h, rawName): HomeState | { error }` (trim; "Name the tab." when empty; new id `t${Date.now().toString(36)}`; becomes active); `renameTab(h, id, rawName): HomeState | { error }`; `deleteTab(h, id): HomeState` (the tab with id `home` and the last remaining tab can't be deleted → returns `h`; if the active tab is deleted, active becomes the first tab); `SNAPSHOTS_KEY = "howlet_home_snapshots_v1"`; `type Snapshots = Record<string, HomeState>`; `loadSnapshots(): Snapshots`; `saveSnapshot(s, rawName, h): Snapshots | { error }` (trim + lower-case; deep copy via `structuredClone`); `deleteSnapshot(s, name): Snapshots`; `applySnapshot(snap): HomeState` (deep copy; active falls back to the first tab when missing).
- `HomePage` tab bar: tabs (double-click or a ✎ button renames inline), **+ Tab** (inline name input), ✕ on every tab except `home` with a two-step "Delete tab?" confirm; a **Layouts** menu: Save current… (name input; overwriting an existing name asks to confirm), Load ▸ (names; replaces the current Home after a confirm), Delete ▸, and **Restore default** (replaces Home with `firstRunHome()` after a confirm). Use Fluent `Menu`/`Dialog`; no `window.prompt`/`confirm`.

- [ ] **Step 1: Failing tests** — `homeState.test.ts` covering: add (empty name error; new tab active), rename (empty error), delete (home protected; last tab protected; active fallback), snapshots save/load/delete round trip with deep copies (mutating the saved snapshot object doesn't change what `applySnapshot` returns later), `applySnapshot` active fallback.
- [ ] **Step 2–4:** fail → implement → `npx vitest run`, `npx tsc --noEmit`, `npm run build`.
- [ ] **Step 5: Commit** — `"Frontend: Home tabs (create/rename/delete) and saved layouts"`.

---

### Task 4: Help page

**Files:**
- Create: `frontend/src/pages/HelpPage.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx` (a "Help & glossary" link card), `frontend/src/App.tsx` (render `HelpPage` when the route is `settings` with `params[0] === "help"`), `frontend/src/lib/commands.ts` (+ test) — `HELP`, `?`, `ABOUT`, `FAQ` go to `{ kind: "page", page: "settings", params: ["help"] }`.
- Test: `frontend/src/lib/commands.test.ts` (update the HELP expectation), `frontend/src/pages/HelpPage.test.tsx`

**Interfaces:**
- `HelpPage()` — the classic HELP content (`src/howlet/dashboard.html` lines ~639–772: About, Glossary, Commands, Blocks, Charting, FAQ, Tips, "Plug this into your AI", Sources), rewritten for the React app: the logo; a jump-link nav (buttons that `scrollIntoView` their section — the page body is not the scroll container); command table updated to the React command box (Ctrl+K, `AAPL`, `AAPL FA/GP/HDS/OPT`, `buffett`, page names, `ALERT AAPL > 350`) and rail pages (Ctrl+1–7); the Blocks section lists all 18 block types; glossary and FAQ text kept. Plain JSX + Fluent text components; no `dangerouslySetInnerHTML`; external links via `safeHref`.
- `HelpPage.test.tsx`: renders, contains the section headings, and every jump button scrolls (`scrollIntoView` mocked and called).

- [ ] **Steps:** failing tests → implement → full checks → commit `"Frontend: Help page (settings/help) and HELP command"`.

---

### Task 5: Backend — tracked managers and holder actions; frontend wiring

**Files:**
- Modify: `src/howlet/views.py`, `src/howlet/dashboard.py`, `tests/test_dashboard.py` (or the views test file that covers these views — follow existing patterns and fixtures), `frontend/src/lib/api.ts`, `frontend/src/lib/settings.ts` (+ test), `frontend/src/pages/SettingsPage.tsx`, `frontend/src/components/OwlChips.tsx` (+ test), `frontend/src/pages/stock/HoldersTab.tsx`, `frontend/src/pages/smart/panels.tsx` (consensus), `frontend/src/shell/AlertsBell.tsx`, `README.md` / `CLAUDE.md` only if they document these endpoints' parameters.

**Interfaces:**
- `views.py`:
  - `resolve_managers(managers: Optional[list[str]]) -> dict[str, str]` — `None`/empty → `FAMOUS_INVESTORS` (today's behaviour). Otherwise for each entry: stripped + lower-cased; a preset label → `{label: FAMOUS_INVESTORS[label]}`; an all-digit string of 4–10 chars → `{entry: entry}` (a raw CIK); anything else ignored. If nothing valid remains, fall back to presets.
  - `consensus_view(svc, min_managers=2, limit=20, managers: Optional[list[str]] = None)`, `holders_view(svc, symbol, managers=None)`, `filing_alerts_view(svc, managers=None)` use `resolve_managers(managers)` instead of `FAMOUS_INVESTORS`.
  - `holders_view` adds to each holder an `action` field: compare the holding's share count (aggregated by CUSIP) with the same CUSIP in that manager's **previous** 13F-HR (`list_13f_filings(cik, limit=2)`, `cached_information_table` — immutable and disk-cached): `"new"` (absent in prior), `"added"` (more shares), `"trimmed"` (fewer), `"held"` (equal), or `null` when there is no prior filing. Only managers that currently hold the symbol are looked up (bounded extra SEC calls, cached forever after). Existing fields unchanged.
- `dashboard.py`: `/api/consensus`, `/api/holders/<symbol>`, `/api/filing-alerts` read an optional `managers` query param (comma-separated) and pass the list (or `None` when absent/blank).
- Python tests: `resolve_managers` (None → presets; preset label; raw CIK; junk ignored; all-junk → presets) and `holders_view` actions with the existing fake services (one manager whose prior filing has fewer shares → "added"; one with no prior holding → "new"). Existing tests stay green.
- Frontend:
  - `Settings.trackedManagers: string[]` (default `[]` = all presets; `mergeSettings` keeps only non-empty strings, lower-cased, deduped) + test.
  - `api.consensus`, `api.holders`, `api.filingAlerts` append `&managers=` / `?managers=` when `trackedManagers` is non-empty (read via `useSettings.getState()` at call time); the holders memo key includes the managers list.
  - Settings → Defaults gains **Tracked managers**: checkboxes for the 14 presets (from `/api/managers`) plus a "Add CIK" input for custom CIKs (digits only, 4–10) shown as removable tags; "All presets" when the list is empty.
  - `Holder` type gains `action: "new" | "added" | "trimmed" | "held" | null`; 🦉 chips append the action ("🦉 buffett · 22.0% · trimmed"; nothing when null/held); the Holders tab gets an "Last quarter" column.

- [ ] **Steps:** Python tests first (fail) → implement backend → `PYTHONPATH=src pytest tests/ -q` + `ruff check src/ tests/` → frontend tests first (settings merge, OwlChips action text) → implement → `npx vitest run`, `npx tsc --noEmit`, `npm run build` → verify with curl against a running server if available (`/api/holders/AAPL` includes `action`; `/api/consensus?managers=buffett,ackman` returns 2 managers) → commit `"Tracked managers and 13F holder actions (backend + UI)"`.

---

### Task 6: Retire /classic, docs, live pass

**Files:**
- Delete: `src/howlet/dashboard.html`
- Modify: `src/howlet/dashboard.py` (remove `/classic` and `_HTML_PATH`; `/` serves `static/app/index.html`, and if the build is missing returns a small plain-text 503 "Dashboard build missing — run `npm run build` in frontend/"), `pyproject.toml` (drop `dashboard.html` from package-data), `tests/test_dashboard.py` + `tests/test_smoke.py` (replace classic-page assertions: `/` serves the React app; `/classic` is 404), `frontend/src/lib/legacy.ts` (keep reading classic keys — users' data — but drop comments that say "classic owns"), any remaining `/classic` links in `frontend/src` (grep; e.g. PlaceholderPage — delete it if now unused), `CLAUDE.md` (module map: drop `dashboard.html` row, `dashboard.py` = Flask wiring + serves the React build; Status: the React app is the only UI, list its pages; remove classic-only gotchas that no longer apply — the `#tape` reduced-motion bullet and the "13 form controls font-size" bullet move to a single "historical (classic UI)" note or are removed; keep everything still true), `README.md` (screenshots/paths/instructions that mention the old UI), `docs/superpowers/plans/2026-10-23-react-shell-followups.md` (note /classic retired).
- Test: Python + frontend suites.

**Interfaces:** none new.

- [ ] **Step 1:** `grep -rn "classic" frontend/src src/howlet tests README.md CLAUDE.md` and list every hit in the report before editing.
- [ ] **Step 2:** Update tests first (`/classic` → 404; `/` serves `<div id="root">`; missing-build 503 via monkeypatching the index path) and see them fail.
- [ ] **Step 3:** Delete `dashboard.html` and make the edits above.
- [ ] **Step 4:** `PYTHONPATH=src pytest tests/ -q`, `ruff check src/ tests/`, `npx vitest run`, `npx tsc --noEmit`, `npm run build`.
- [ ] **Step 5: Commit** — `"Retire the classic dashboard; React app is the only UI"`.
- [ ] **Step 6: Live pass (controller)**: every rail page and stock tab; add one of each of the 18 block types to a new Home tab; save/load/delete a layout; rename/delete a tab; Help jump links; Settings tracked managers change consensus/holders/bell; chips show actions; `/classic` 404s; console clean.
