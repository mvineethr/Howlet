# CLAUDE.md - dev brief for Howlet

## What this is

A free, no-API-key, open-source Bloomberg-style terminal built on SEC
EDGAR 13F data ("what is Warren Buffett buying"), grown into a full
market terminal: web dashboard (`howlet dashboard`), CLI, Python
library, and an MCP server (`howlet mcp`, 27 tools) so any AI agent
can drive it. Everything is verified live against the real APIs, not
just offline mocks - that habit has caught a real bug almost every
session (see Gotchas).

See `HANDOVER.md` for the full session-by-session history of what was
built, why, and what broke along the way. `README.md` is the user-facing
doc. Tests: `pytest tests/` - all offline/mocked.

## Module map (src/howlet/)

| Module | What it does |
| --- | --- |
| `client.py` | SEC EDGAR client: CIK search, 13F filings (paginated), info-table XML parsing, retry/backoff, ~10 req/s self-throttle |
| `models.py` | `FilingSummary`, `Holding` (values in whole USD - see Gotchas), `HoldingChange` |
| `diff.py` | Q/Q holdings diff by CUSIP (aggregates multi-entry CUSIPs first) |
| `form4.py` | Form 4 insider transactions: issuer CIK -> ownershipDocument XML, non-derivative rows only (P/S = the open-market signal) |
| `consensus.py` | Cross-manager "smart money consensus" over `presets.py` |
| `cache.py` | Parsed holdings + Form 4 transactions cached by accession number (filings are immutable) |
| `tickers.py` | CUSIP->ticker via OpenFIGI keyless tier, disk-cached forever, prefers US composite listing; misses fall back to SEC company_tickers.json name matching (`views._apply_name_fallback` + `fundamentals.name_to_ticker`) |
| `market.py` | Yahoo v8 chart endpoint (keyless): quotes, full OHLCV history, world tape |
| `fundamentals.py` | SEC XBRL companyfacts: annual 10-K metrics, shares outstanding (dei) |
| `indicators.py` | Pure-math studies: SMA/EMA/RSI/MACD/Bollinger/ORB |
| `risk.py` | Pure-math portfolio risk: volatility, max drawdown, Sharpe |
| `screener.py` | Screener over a curated universe (SEC fundamentals + chart quotes only) |
| `news.py` | RSS aggregation: Yahoo/CNBC/CNBC Earnings/MarketWatch/Google News/Seeking Alpha/SEC; per-ticker feeds |
| `events.py` | Earnings date + analyst mix (Yahoo, crumb-authed), DEF 14A proxies (EDGAR), Fed RSS |
| `options.py` | Options chains (Yahoo, crumb-authed) - EXPERIMENTAL, de-emphasized per user |
| `macro.py` | Treasury yield curve (keyless), BLS unregistered tier, FRED (optional key) |
| `crypto.py` | Top coins by market cap: CoinGecko keyless tier, Coinpaprika fallback, 60s TTL cache; degrades to empty |
| `regulatory.py` | SEC rulemaking/notices from the Federal Register API (keyless, official); degrades to empty |
| `fulltext.py` | EDGAR full-text search (efts.sec.gov, keyless official): search filing CONTENT since 2001 |
| `fx.py` | ECB daily FX reference rates via Frankfurter (`api.frankfurter.dev/v1` - old .app domain 301s); derived cross-rate matrix, 1h cache; degrades to {} |
| `nport.py` | N-PORT fund holdings: ticker->series via company_tickers_mf.json, series-scoped browse-edgar for accessions, primary_doc.xml parse. UITs (SPY) have no NPORT trail |
| `yahoo_auth.py` | Yahoo cookie+crumb workaround for walled endpoints; consumers must degrade, never raise |
| `views.py` | Shared JSON view layer - Flask endpoints AND MCP tools both wrap these |
| `dashboard.py` | Flask wiring only; serves the React app at `/` (from `frontend/`, built into `static/app/`) and the classic UI (`dashboard.html`, single file, vanilla JS) at `/classic` until plan 2 ports the remaining screens |
| `mcp_server.py` | FastMCP stdio server, 27 tools (optional dep: `pip install "howlet[mcp]"`) |
| `frontend/` | React + Fluent UI v9 app (Vite), builds into `static/app/`; served at `/`. Old UI at `/classic` until plan 2 completes |

## Hard rules

- **No required API key, ever.** FRED (`FRED_API_KEY`) and OpenFIGI
  (`OPENFIGI_API_KEY`) are optional enrichers; everything must work
  without them. Never add a paid wrapper as a default path.
- **Always require a real User-Agent with contact email** for SEC
  (`EDGAR_USER_AGENT`). Don't relax the validation in `EdgarClient`.
- **Keep every self-throttle**: SEC ~10 req/s, Yahoo 0.25s, OpenFIGI
  3s/batch keyless. Good-citizen behavior, not a technical limit.
- **SEC data is authoritative; market data is decoration.** Yahoo/
  OpenFIGI/RSS failures must degrade to missing values or "unavailable",
  never break the 13F views. Anything built on `yahoo_auth.py` (events,
  options) is the fragile tier and must never raise.
- **No paywalled or proprietary components in the UI.** Charting is
  KLineChart (Apache-2.0) - TradingView was removed because its free
  widget caps stacked indicators behind a subscription.
- **Verify live before calling anything done.** Offline mocks have
  repeatedly agreed with the code and disagreed with reality. This now
  extends to the docs: CLAUDE.md and HANDOVER.md have both been wrong
  about shipped state at times. Check PyPI/git, don't read a claim.
- **Never put a real credential in any repo-tracked file - `.pypirc`
  only, written by hand outside the repo.** `pyproject.toml` is
  specifically dangerous for this: it ships straight into every
  sdist/wheel you build and upload. A PyPI token pasted there was
  caught in a `git diff` before commit; treat any secret shown in a
  chat transcript as needing rotation too, not just "never committed."
- **No database.** Filings are immutable, so accession-keyed flat files
  under `~/.howlet/` are the correct structure, not a stopgap: a full
  cross-filing aggregation walk (2,720 rows -> 1,287 CUSIPs across every
  cached filing, 796 KB total) runs in a **median 8.4 ms**. Every slow
  path here is a network throttle a DB cannot touch. If it ever is
  needed, use stdlib `sqlite3` behind the existing two-method
  `FilingCache` seam - never a service.
- **UI colour lives in `:root` only.** All dashboard colour comes from
  CSS custom properties (`--bg`, `--panel`, `--elev-1/2`, `--hair`,
  `--border`, `--amber`, `--amber-dim`, `--text`, `--dim`, `--up`,
  `--down`, `--cyan`). Anything themed through JS must READ those tokens,
  never restate them.

## Gotchas (each cost a live debugging session - don't re-learn them)

- **13F `<value>` is whole dollars post-Jan-2023** (SEC amendment).
  Pre-2023 filings used thousands - old filings would read 1000x low.
- **SEC's `output=atom` company search is broken server-side** (Perl
  array refs in titles). Parse the HTML table instead. And an
  exact-match query skips the results table entirely (renders that
  company's filing list) - `search_company_cik` reads the
  `span.companyName` header on that layout.
- **Famous managers migrate filer entities.** Appaloosa Management LP
  (1006438) stopped filing in 2016 (now Appaloosa LP, 1656456);
  Greenlight's 1079114 stopped after 2023 (now DME Capital, 1489933).
  When adding a preset, check its latest 13F-HR is CURRENT, not just
  that the name matches.
- **One filing can list one CUSIP many times** (Berkshire lists AAPL
  5x). Always aggregate by CUSIP first. Alphabet GOOGL/GOOG and Lennar
  LEN/LEN.B as separate rows are CORRECT (different CUSIPs).
- **Submissions pagination**: `filings.files[]` pages are flat dicts,
  `recent` is nested. Both under `data["filings"]`.
- **OpenFIGI's first listing isn't always the US ticker** (Chevron
  returns stale "CHV" before "CVX"). Prefer `exchCode == "US"`;
  normalize BRK/B -> BRK-B for Yahoo.
- **Yahoo `chartPreviousClose` is the close before the RANGE start**,
  not yesterday - naive change_pct shows range drift as a day move.
  With daily bars use the second-to-last bar as previous close.
- **Yahoo walled off v7/quote, v10/quoteSummary, v7/options** behind
  cookie+crumb (see `yahoo_auth.py`). The v8 chart endpoint is still
  open - the screener deliberately uses only that plus SEC data.
- **Treasury's OData feed**: values are under `<m:properties>` (metadata
  namespace). Parse by local tag name; a namespace-based parser AND its
  hand-built fixture both had the same bug once (tests green, live {}).
- **XBRL 10-Ks tag quarterly comparatives too** - filter duration
  entries to >=300-day spans or Q4 values masquerade as annual.
- **KLineChart is vendored** at `static/klinecharts.min.js` (+ LICENSE) for `/classic`, and installed from npm (pinned 9.8.12) for the React app,
  served by Flask's default `/static/` - no CDN at runtime. (When it was
  CDN-loaded: the path is `dist/umd/...`; plain `dist/` 404s silently.)
- **SEC resets stale keep-alive connections** on long-lived sessions
  (WinError 10054) - `_get` retries ConnectionError like a 5xx, and the
  Flask app maps every `requests.RequestException` to a JSON 502 (an
  HTML error page shows as "Unexpected token '<'" in the widgets).
- **Form 4 `primaryDocument` carries an XSL viewer prefix**
  (`xslF345X06/form4.xml`) - the raw XML is the bare filename in the
  filing folder. Prices can be footnote-only (RSU vests) -> None, and
  the same filing's derivativeTable would double-count the vest if
  parsed alongside the non-derivative rows.
- **TradingView-style embeds fail silently on a wrong script URL** - no
  console error, no iframe. Verify third-party URLs with curl first.
- **Date-only strings (e.g. Federal Register `publication_date`) must
  not go through `new Date(...)` display formatting** - JS parses them
  as UTC midnight, so US timezones render the previous day.
- **A same-named PyPI package isn't just a listing clash - it can be an
  `import`-level collision.** Distribution name and top-level package
  name aren't required to match. Before adopting a package name, pull
  the existing project's actual sdist/wheel and check its real
  importable module name, not just whether the PyPI slug is taken.
  This is why the project is `howlet`, not `edgar` (py-edgar's module
  is also `edgar`) or `edgar-terminal` (same problem, different label).
- **CI runs bare `pytest tests/ -v`, not `python -m pytest`.** The
  latter puts cwd on `sys.path`; the former doesn't. A cross-module
  test import (`from tests.test_form4 import ...`) worked locally by
  accident and failed on every CI matrix leg on the first real push.
  Same-directory imports (`from test_form4 import ...`) resolve under
  both invocations. When CI disagrees with a green local run, run CI's
  *exact* command locally before trusting either result.
- Docker Desktop here sometimes evicts freshly built images; rebuild.
- **`pip install -e .` breaks silently when the project directory is
  renamed.** The `.pth` file records an absolute path, so after the
  edgar -> howlet rename `site-packages/__editable__.howlet-0.8.0.pth`
  still pointed at `D:\src\edgar\src`: `pip show howlet` reports 0.8.0
  installed while `import howlet` fails, `howlet --version` throws, and
  bare `pytest tests/` collects nothing. `PYTHONPATH=src` is the
  workaround; `pip install -e .` from the real root is the fix. Also why
  `.claude/launch.json` now sets `PYTHONPATH: src`.
- **KLineChart's theme is a SECOND copy of the palette, in JS.** Its
  styles come from a JS API, so it is invisible to CSS-token work and
  will keep rendering the old brand after `:root` changes. `initKlineChart`
  now reads the tokens via `getComputedStyle(document.documentElement)`.
  Grep the JavaScript for hex literals before changing any colour.
- **You cannot grep for a missing declaration.** 13 form controls set
  `font-family: inherit` but never `font-size`, so they silently rendered
  at the UA default (13.33px, proportional metric) inside a monospace
  terminal. Only a computed-style probe of the live DOM finds this class
  of bug - the source rules look complete.
- **`prefers-reduced-motion` must restore layout preconditions, not just
  kill animation.** `#tape` is parked offscreen by `padding-left: 100%`
  and walked in by its keyframes; disabling the animation alone hides the
  ticker permanently, so the block also resets `padding-left: 0`.
- **`:focus-visible` does not match a scripted `.focus()`** (Chrome wants
  real keyboard interaction). Verify focus styles with an actual Tab
  keypress or you will "find" a bug in correct CSS.
- **Vite dev server (5173) is a different origin -> separate localStorage.** Your real watchlists/alerts only appear at `:8813`; always verify there.

## Caches (all under `~/.howlet/`)

`holdings/` (by accession, immutable), `form4/` (same), `cusip_tickers.json` (forever;
network failures are NOT cached), `screener_cache.json` (per ticker per
day). Browser localStorage holds watchlists, personal portfolio, layout.

## Status

All working and verified live. React app at `/` (from `frontend/`, built into `static/app/`); classic UI at `/classic` until plan 2 ports the remaining screens. Classic has **11 screens**, one URL, no routing:
HOME (blank slate, "+ ADD BLOCK" picker over 17 widget types, "+ TAB"
user tabs, per-block wide/tall toggles, named layout snapshots, multiple
named watchlists, RESTORE CLASSIC LAYOUT), PORT, DES (vendored
KLineChart, unlimited indicators + drawing, studies incl. ORB, BACK
button), FA, HDS, NEWS (7 feeds), MY, MKTS (STOCKS/CRYPTO toggle,
separate spaces, remembered), EQS, ECO (Treasury/BLS/FRED/Fed + SEC
RULEMAKING), PF risk, OPT (experimental). Each surface exists as CLI +
`/api/*` + MCP tool via `views.py`: Form 4 insiders, 13F position
history, insider-buy screening, 13F filing alerts (topbar bell, 30-min
poll), EDGAR full-text search, company filings feed, N-PORT fund
holdings (ARKK verified; UITs like SPY correctly error), FX cross-rate
matrix, crypto top-20, `howlet warm`, EXPORT/IMPORT state backup, CSV
export. **MCP: 27 tools.** Presets: **14 managers** (Buffett, Burry,
Ackman, Icahn, Tepper, Klarman, Loeb, Dalio, Druckenmiller, Marks,
Li Lu, Einhorn/DME, Fundsmith, Tiger Global), every CIK verified live
against a current 13F-HR. CI (ruff + pytest, 6 legs) and Docker.

**Published and public** (verified live 2026-07-25, not from docs):
`pip install howlet` -> **0.8.0 on PyPI**, the only release; GitHub public
at `mvineethr/Howlet` with `origin/main` == local at `4c75cf7`; CI green
on all 6 matrix legs; 145 offline tests pass; ruff clean. Note `git tag`
is still EMPTY despite the release.

**Dashboard visual layer refreshed** (2026-07-25, uncommitted on branch
`claude/repo-analysis-trader-api-b78191`): tokenized elevation ramp,
brand amber desaturated 100% -> 80% saturation with hue held at exactly
36 (`#ff9900` -> `#eaa53e`), 11px floor raised to 12px, panel surface
treatment, first-ever `:focus-visible` styles, a motion layer with a
`prefers-reduced-motion` block, and the fake blinking "live" dot removed
(it asserted liveness it could not know). Chart theme now reads `:root`.
168/102 line diff, tests still green, verified live in the browser.

React shell live at `/` (2026-10-23): rail, Ctrl+K, settings, Home grid, stock overview + owl chips, alerts bell; News, Markets (stocks/crypto/FX/economy) and Screener pages (2026-10-24); stock page tabs: overview/events/studies/ORB, KLineChart chart, financials, holders/insiders/filings, news, options (2026-10-24); other pages still in `/classic`.

Known-untested: FRED with a real key; pre-2013 SGML filings (should
error clearly, never exercised).

Known-broken, deliberately deferred (audience is 3 desktop users):
`#news-grid` and `#my-grid` set `grid-template-columns` inline with no
media query so they never collapse; the HOME grid's `minmax(420px, 1fr)`
is CLIPPED below 420px by `body { overflow-x: hidden }`.

## Next features (in rough priority order)

1. **Close the remaining loops from 2026-07-25** - `git tag v0.8.0`,
   `pip install -e .` from the real root to fix this machine's broken
   editable install, and ship 0.8.1+ so the live PyPI page picks up the
   README logo/badges (PyPI freezes each release's rendered description
   at upload time). The design branch itself is merged as of this entry.
2. **Schwab Trader API, read-only** - planned in full, not built; blocked
   on Schwab's manual app approval (`Ready for Use`, days). Design is
   fixed by one fact: the **refresh token expires in 7 days, hard, with no
   renewal path**, so it belongs in the fragile tier beside
   `yahoo_auth.py` where "not connected" is a normal state, as an optional
   FRED-style enricher (env creds, token at `~/.howlet/schwab_token.json`,
   gitignored). Verified endpoints: `/trader/v1/accounts/accountNumbers`
   -> hashValue, `/trader/v1/accounts/{hash}?fields=positions`,
   `.../orders`, `.../transactions`, `/marketdata/v1/quotes`. Access
   token 30 min; callback must be `https://127.0.0.1:<port>` exactly.
   Plan: `schwab.py` + 3 views + 3 routes + 3 MCP tools (27 -> 30) + 3
   blocks + `howlet schwab-login` (paste-the-redirect-URL flow, no
   shipped cert) + mocked tests. Zero new dependencies.
3. **N-PORT depth** - disk-cache parsed NPORT filings by accession
   (immutable, same as 13F/Form 4), fund position history across
   months, or fund-vs-13F overlap views. This is the one item that grows
   the cache monthly rather than quarterly, so it is the likeliest
   trigger for revisiting the no-database call.
4. **Finer-grained EDGAR locking** - `edgar_lock` serializes ALL EDGAR
   access; a cold consensus load still blocks the other EDGAR-backed
   panels (mitigated day-to-day by `howlet warm`).

## Session History

One line per session; full narrative for each lives in `HANDOVER.md`.

- **S1** (2026-06-30) - First-ever live SEC verification (Docker); found
  and fixed the `output=atom` Perl-array-ref bug in `search_company_cik`.
- **S2** (2026-07-06 pt1) - Initial Bloomberg-style Flask dashboard +
  market data + news.
- **S3** (2026-07-06 pt2) - Full terminal screens (DES/FA/HDS/PORT) +
  first MCP server.
- **S4** (2026-07-06 pt3) - Analytics, screener, options, macro, events
  modules.
- **S5** (2026-07-07) - KLineChart charting, NEWS/MY tabs, FRED macro.
- **S6** (2026-07-07 pt2) - Customizable blank-slate dashboard: widgets,
  tabs, BACK button.
- **S7** (2026-07-17) - Form 4, 13F position history, expanded presets,
  name-to-ticker fallback, v0.7.0.
- **S8** (2026-07-17 pt2) - Per-widget resize toggles + named layout
  snapshots.
- **S9** (2026-07-17 pt3) - Crypto screen (CoinGecko/Coinpaprika) +
  Federal Register + cleaner topbar.
- **S10** (2026-07-17 pt4) - Review-driven feature sprint: insider-buy
  screening, filing alerts, EDGAR full-text search, N-PORT fund
  holdings, FX matrix, v0.8.0 release prep.
- **S11** (2026-07-17 pt5) - Rebrand `edgar13f`→`Edgar`→`howlet` (PyPI
  `import`-collision discovery), caught+fixed a credential exposure,
  first GitHub push + CI fix, published live on PyPI, owl logo across
  README/PyPI/in-app.
- **S12** (2026-07-18) - Wrote external EB-1A/content docs for S9-S11;
  refreshed this Session History block, Status, and two new Gotchas;
  added the `/handover` slash command. (Sat uncommitted in the working
  tree for a week - see HANDOVER.md's correction note on this entry.)
- **S13** (2026-07-25) - Cold-start audit found the docs stale and the
  editable install broken (and found S12 itself sitting uncommitted);
  planned the read-only Schwab integration; 4-step gated design overhaul
  of `dashboard.html`; measured the no-database decision at 8.4 ms.

## Working rules

1. Plan before touching anything. Write the goal, the steps, and the success criteria first. No edits until the plan exists.

2. Before presenting any answer, try to refute it. Check the case where it fails. If it survives, present it along with the one caveat that matters.

3. Open every reply with the result. "Done: X changed, Y verified." Never open with what you are about to do.

4. Keep replies short by default. No narrating your own process, no restating my question, no summary of what you just said.

5. Do exactly what was asked. If you notice adjacent problems, flag them in one line each. Never silently fix things outside the task.

6. Trust the live system over documentation. Before asserting anything that matters, verify it against the actual files, the actual data, the actual output.
