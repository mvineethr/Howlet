# HANDOVER - edgar13f

Session log for picking this project back up. See `CLAUDE.md` for the
standing dev brief (what the tool is, current status, constraints).
Newest session first.

---

# Session 2026-07-17 (part 4): the full review slate - 6 features + release prep

## What was asked

"Do that all" after a thorough project review: every improvement and
every addition from the review, then a list of what only the user can
do (accounts).

## What was built (each verified live before moving on)

- **Quick wins**: `edgar13f warm` (14 portfolios + 1275 CUSIPs mapped in
  one pre-fetch run, verified), EXPORT/IMPORT full-state JSON backup in
  the tab bar, CRYPTO TOP 20 home block, ⤓ CSV buttons (portfolio/
  changes/consensus/EQS), ruff in CI (3 findings fixed), 2 HTML smoke
  tests. The "newsItemsHtml `<\\span>` typo" from the review turned out
  not to exist - review claim was wrong, nothing to fix.
- **Insider-buy screening**: `_symbol_form4_transactions` helper +
  `insider_buys_view`; CLI `insider-buys`, `/api/insider-buys`, MCP
  `screen_insider_buys`, watchlist-scoped block. Live verify found a
  real signal: OXY President/CEO Jackson bought 4,770 sh @ $52.38
  (2026-06-23); AAPL/JPM/INTC/BA correctly zero.
- **13F filing alerts**: `latest_filings_view` (per-preset newest
  accession, one broken manager can't kill the poll - tested), topbar
  bell polls every 30 min, baseline-then-diff against
  `edgar13f_seen_filings_v1`, optional desktop notifications, MARK ALL
  SEEN. Verified by rewinding Buffett's seen accession live - badge lit
  with his real Q1 filing, dismiss restored state.
- **EDGAR full-text search** (`fulltext.py`, efts.sec.gov) + **company
  filings feed** (list_filings generalized to form_type=None; new
  optional `form` field on FilingSummary). CLI `fts`/`filings`, two MCP
  tools, SEC FILINGS block. Both verified live (AAPL 8-Ks; phrase
  search returns real hits with working archive links).
- **FX matrix** (`fx.py`): Frankfurter/ECB - NOTE the old
  api.frankfurter.app domain 301s; use api.frankfurter.dev/v1. Cross
  rates derived from one USD-based call, 1h cache. Verified EUR->JPY
  185.65 against tape (162.35 x 1.1435 ✓).
- **N-PORT fund holdings** (`nport.py`): company_tickers_mf.json ->
  (trust CIK, seriesId); browse-edgar filtered BY SERIES ID (the trust
  CIK alone mixes its funds); primary_doc.xml parsed by local name.
  ARKK verified live ($6.48B net, Tesla 9.74% top). SPY/UITs correctly
  raise a clear LookupError - they don't file NPORT-P.
- **Release prep**: v0.8.0, CHANGELOG, README/CLAUDE.md updated (also
  fixed stale "KLineChart loaded from jsDelivr CDN" claim - it's
  vendored), dist rebuilt + twine-checked.

## State

145 offline tests green, ruff clean, all 7 new dashboard blocks
verified rendering live data in the browser, zero console errors.
MCP: 27 tools.

---

# Session 2026-07-17 (part 3): crypto screen, Federal Register, cleaner topbar

## What was asked

From the API-list review: wire in Federal Register (candidate #3), and
a crypto screen "along with stocks but under a toggle - not in the same
space". Also remove the example-hint placeholder from the command box.

## What was built

- **`crypto.py`**: CoinGecko keyless `/coins/markets` (probed live
  first) with automatic Coinpaprika fallback, normalized rows, 60s
  in-memory TTL cache, degrades to ("", []). `crypto_view` +
  `/api/crypto` + MCP `get_crypto_markets`.
- **MKTS STOCKS/CRYPTO toggle**: two modes in separate spaces, choice
  remembered (`edgar13f_mkts_mode`). The old 5-symbol CRYPTO section
  was removed from `MARKET_SECTIONS` (and its test updated to assert
  it's ABSENT). Crypto side: top-50 table w/ price, 24h %, mkt cap,
  volume, 24h range, "source: coingecko|coinpaprika" label.
- **`regulatory.py`**: Federal Register API (keyless, official) SEC
  documents; `regulatory_view` + `/api/regulatory` + MCP
  `get_sec_rulemaking` + SEC RULEMAKING panel on ECO. MCP now 21 tools.
- **Command box placeholder removed** per user.
- Tests 132 (fixtures trimmed from live payloads captured 2026-07-17).

## Live-found bug #7: date-only strings render a day early

Federal Register `publication_date` ("2026-07-17") fed to
`new Date(...).toLocaleString()` renders as "7/16/2026, 7:00:00 PM" in
US timezones (parsed as UTC midnight). Fixed by passing the date string
through verbatim in the source label. Gotcha added to CLAUDE.md.

## Verified live (browser)

Stocks side has NO crypto section; CRYPTO toggle renders top-50 with
BTC $64,123 / $1.29T cap (cross-checked against the Yahoo tape's
BITCOIN 64,120); ECO shows same-day Federal Register notices (first
item matched the raw API probe). NOTE: Python edits need a dashboard
server restart - only dashboard.html is re-read per request (this
nearly passed as "verified" against stale code).

---

# Session 2026-07-17 (part 2): widget resize + named layout snapshots

## What was asked

Per-widget resize, and saving layouts "like a memory" (single user, no
profiles needed). Plus a review of two public-API lists for candidate
integrations (assessment delivered in chat; no new sources wired in -
top keyless candidates recorded in CLAUDE.md's next-features list).

## What was built

- **Per-widget resize**: every dashboard block header now has ↔ (toggle
  full width, same grid mechanic as the built-in `wide` widgets) and ↕
  (double height: `.widget.tall .panel-b` max-height 420 -> 860px).
  Stored as `w.wide` / `w.tall` booleans on the widget entry in the
  layout; toggling flips classes in place so the block is NOT refetched
  just for a resize.
- **Named layout snapshots**: LAYOUTS: [select] SAVE/LOAD/DEL in the
  dashboard tab bar. SAVE deep-copies the whole layout (all tabs,
  blocks, sizes) into `edgar13f_layouts_v1` under a prompted name;
  LOAD replaces the live layout (with confirm); DEL removes a snapshot.
  All localStorage, consistent with watchlists/portfolio.

## Verified live (browser)

Toggled ↔/↕ on the insiders block (class + persisted booleans checked),
saved snapshot "work", deleted the insiders block, LOAD restored it with
its wide+tall sizing intact. Native prompt()/confirm() dialogs were
stubbed via console during automation - they block the browser-pane
tools - but the click path exercised was the real one.

---

# Session 2026-07-17: roadmap cleared - Form 4, position history, presets, ticker fallback, v0.7.0

## What was asked

"Follow the order, complete them one by one" - the whole CLAUDE.md
roadmap: (1) Form 4 insider transactions, (2) historical position
charts, (3) expand presets, (4) name-based ticker fallback,
(5) publishing checklist.

## What was built

- **Form 4 insider transactions** (`form4.py` + `Form4Cache` in
  cache.py): issuer CIK -> form "4" filings (via a new generic
  `EdgarClient.list_filings(cik, form_type)`; `list_13f_filings` is now
  a wrapper) -> ownershipDocument XML, parsed namespace-tolerantly.
  Non-derivative rows only (the derivativeTable would double-count RSU
  vests). Surfaces: CLI `insiders` (P/S only by default, `--all` for
  everything), `/api/insiders/<symbol>`, MCP `get_insider_transactions`,
  INSIDER TRANSACTIONS dashboard block (new `needs: "symbol"` picker
  config).
- **13F position history**: `position_history_view` walks N quarters of
  cached filings, aggregates by CUSIP, matches query as ticker (via the
  resolver, no new lookups) / raw CUSIP / issuer-name substring.
  Surfaces: CLI `history`, `/api/position-history/<mgr>/<query>`, MCP
  `get_position_history`, 13F POSITION HISTORY dashboard block with
  amber value bars + share-change deltas (new `needs: "manager-symbol"`
  picker config). MCP is now 19 tools.
- **Presets 4 -> 14 managers**: tepper/appaloosa 1656456, klarman/
  baupost 1061768, loeb/thirdpoint 1040273, dalio/bridgewater 1350694,
  druckenmiller/duquesne 1536411, marks/oaktree 949509, lilu/himalaya
  1709323, einhorn/greenlight 1489933 (DME Capital - see below),
  fundsmith 1569205, tigerglobal 1167483. EVERY CIK verified live two
  ways: name search AND latest 13F-HR is current (2026-03-31).
- **Name-based ticker fallback**: `fundamentals.name_to_ticker`
  (normalized exact match against company_tickers.json titles, trailing
  noise tokens stripped, first class in file order wins ->
  GOOGL not GOOG) wired into portfolio/holders views via
  `views._apply_name_fallback`; successes are written back into the
  resolver's disk cache via the new `CusipTickerResolver.learn`.
  Verified live: Berkshire's CHUBB LTD SWITZ / H1467J104 -> CB @ $353.
- **v0.7.0 published-ready**: CHANGELOG.md, version bump, sdist+wheel
  built, `twine check` PASSED, wheel verified to contain dashboard.html
  + vendored klinecharts + form4.py. Repo `git init`ed with the initial
  commit so the CI workflow finally has a repo to run in.

## Live-found bug #7: EDGAR exact-match company search redirect

An exact-name query ("third point") skips the results table - EDGAR
renders that company's own filing list instead, and the old parser
returned garbage rows ({"name": "Documents", "cik": None}) from the
filing table. `search_company_cik` now detects `span.companyName` and
reads the name + CIK from the header. Found because preset
verification searched "greenlight capital" live.

## Also learned live (now in CLAUDE.md gotchas)

- Form 4 `primaryDocument` is an XSL viewer path (`xslF345X06/form4.xml`);
  the raw XML is the bare filename. Prices can be footnote-only -> None.
- Famous managers migrate filer entities: Appaloosa Management LP
  (1006438) stopped filing in 2016 (Appaloosa LP 1656456 now files);
  Greenlight's 1079114 stopped after 2023-12-31 - Einhorn files as DME
  Capital Management LP (1489933). Name match alone is not enough;
  check the latest 13F-HR is current.
- SEC titles vs 13F issuer names disagree in suffixes AND jurisdiction
  tags ("Chubb Ltd" vs "CHUBB LIMITED" vs "CHUBB LTD SWITZ").

## Verified live this session

- `insiders AAPL`: 0 open-market buys, 14 sells $111.7M across 15
  Form 4s (Cook/Parekh/O'Brien/Levinson rows, prices in AAPL's real
  range); same numbers in the dashboard block.
- `history buffett AAPL --quarters 10`: 905,560,000 -> 789,368,450 ->
  400,000,000 -> 300,000,000 -> ... -> 227,917,808 shares - matches
  Berkshire's publicly reported AAPL trim exactly. Same data in the
  dashboard block after a server restart (a stale server 404s new
  routes as "Unexpected token '<'" - that's just Flask needing a
  restart, not bug #6 again).
- `holdings tepper`: Appaloosa's real Q1-2026 book (AMZN $900M top
  position, Alibaba, Vistra...).
- Chubb name-fallback via `/api/portfolio/buffett?top=30`.

## Tests

111 -> 122, all offline/mocked (`pytest tests/`): Form 4 parsing from a
captured live AAPL filing (footnote price -> None, derivative rows
excluded, XSL prefix stripped), position history (chronology,
multi-entry aggregation, name fallback, 404), exact-match search
redirect, name normalization, portfolio Chubb fallback + learn().

## What's still open

- **Publish to PyPI / push to GitHub** - artifacts are built and
  checked in `dist/`, repo is committed locally; pushing and
  `twine upload` need the user's accounts/credentials.
- Known-untested: FRED with a real key; pre-2013 SGML filings.
- First `holders`/`consensus` run with the 14-manager roster will be
  slow (OpenFIGI keyless mapping for ~10 new portfolios, Bridgewater
  and Tiger are big); disk-cached forever afterwards.

---

# Session 2026-07-07 (part 2): customizable dashboard, tabs, back button

## What was asked

Blank-slate HOME where the user picks blocks; multiple watchlists with
news scoped to only those symbols; a "+" for user-created tabs; a back
button on the security screen (which itself must NOT change); plus the
pre-publish items (CLAUDE.md cleanup, vendor KLineChart, CI).

## What was built

- **CLAUDE.md rewritten** from a session diary into a concise brief:
  module map, hard rules, gotchas list, status, roadmap. History lives
  here in HANDOVER.md only.
- **KLineChart vendored** into `src/edgar13f/static/` (+ its Apache-2.0
  LICENSE file); served via Flask's default /static/; no CDN at runtime.
  package-data updated.
- **GitHub Actions CI** (.github/workflows/ci.yml): ubuntu+windows x
  py3.10/3.12/3.13, offline test suite. (Repo isn't `git init`ed yet.)
- **Customizable dashboard** (new default screen `screen-dash`):
  - localStorage layout {tabs:[{id,name,widgets}], active}; blank HOME
    by default + RESTORE CLASSIC LAYOUT preset button.
  - 10 widget types: 13F portfolio / Q/Q changes (per manager),
    consensus, watchlist / watchlist-news / watchlist-events (per named
    list), market news, Fed, yield curve, world markets. Widgets have
    remove x, config label, periodic refresh (60s watchlists, 300s news).
  - "+ TAB" creates named tabs (deletable except HOME).
  - Multiple named watchlists (`edgar13f_watchlists_v1`, old single-list
    key migrated to "default"; MY screen now reads the "default" list so
    it stays in sync with home widgets).
- **BACK button** on the DES chart header; `showScreen` records the
  screen you came from (state.backTo). DES content otherwise untouched.
- PORT screen (classic manager view) kept as-is, reachable via manager
  dropdown/PORT command; its consensus/news panels now lazy-load on
  first visit instead of at boot.

## Live-found bug #6: SEC resets stale keep-alive connections

The widget grid's parallel calls surfaced ConnectionResetError 10054
from data.sec.gov on the long-lived shared session - `_get` only
retried HTTP 429/5xx, so the exception propagated and Flask returned an
HTML 500 page, which the frontend showed as "Unexpected token '<'".
Fixed twice over: `_get` now retries `requests.ConnectionError` with
the same backoff, and the Flask errorhandler was widened from HTTPError
to `requests.RequestException` so every upstream failure is a JSON 502.
Tests 108 -> 111.

## Verified live (browser)

- Blank slate on first load; klinecharts served locally (CDN removed).
- Built a layout programmatically via the same code paths as the picker:
  13F portfolio (buffett, $263.10B/29 positions), custom "ai-stocks"
  watchlist (NVDA/MSFT/GOOGL live quotes, inline add/remove), watchlist
  news showing ONLY those 3 names, yield curve; MISC tab holding a Fed
  widget. Layout + tabs survived a server restart.
- Add-picker opens with all 10 types; tab switching works.
- NVDA click in a widget -> DES -> BACK -> dashboard intact.

---

# Session 2026-07-07: KLineChart, NEWS/MY tabs, FRED

## What was asked

User hit TradingView's free-widget limit (2 stacked indicators, more =
subscription) and wants everything un-paywalled for the open-source
release. Also: a dedicated NEWS tab with more free sources, a
personalize (MY) tab (watchlist + scoped news + events, click-through to
DES), FRED enabled, options work paused.

## Decisions

- **KLineChart** (Apache-2.0) replaces the TradingView embed: ~30
  built-in indicators with NO stacking limit, drawing overlays, and it
  renders our own OHLCV - no third party controls the chart. CDN gotcha:
  the UMD build is at `dist/umd/klinecharts.min.js`; `dist/<file>` 404s
  (hit this live - klinecharts loaded as undefined until fixed).
- WATCH screen folded into the new MY tab (same localStorage key, WATCH/W
  still route there). OPT stays functional but off the F-key bar.

## Changes

- `market.py`: Quote.history_open added; parser keeps full OHLCV aligned
  after None-gap dropping. `views.security_view` returns the arrays.
- `news.py`: MARKET_FEEDS + Google News Business, CNBC Earnings, Seeking
  Alpha Market Currents. Per-ticker: TICKER_FEED_URLS (Yahoo + Google
  News search + Seeking Alpha per-symbol), merged/deduped.
- `macro.py`: FRED_SERIES + get_fred_snapshot(); macro_view includes
  fred_series when FRED_API_KEY set (untested with a real key so far).
- `dashboard.html`: KLineChart init/dark styles/indicator picker with
  removable chips/draw toolbar; NEWS + MY screens; fkeys now
  HOME/DES/NEWS/MY/MKTS/EQS/ECO/PF/HELP.
- Tests 106 -> 108 (FRED snapshot, multi-feed ticker news, OHLCV).

## Verified live (2026-07-07)

- AMZN DES: 123 candles; last bar O 243.79 H 246.04 L 240.88 C 244.16
  V 37.57M - matches the user's own TradingView screenshot exactly.
- 10 indicators stacked simultaneously, removed cleanly; drawing overlay
  armed without error.
- NEWS tab: 60 wire items across CNBC/CNBC Earnings/MarketWatch/Google
  News/Seeking Alpha, 15 Fed items, 8 earnings/analysis.
- MY tab: 7 watchlist quotes; 40 scoped news items; events table with
  real earnings dates (AAPL 07-30, MSFT 07-29, NVDA 08-26, AMZN 07-30,
  TSLA 07-22) + analyst views + last DEF 14A per name.

## Open

- FRED path needs a real-key test once the user signs up.
- Consider vendoring klinecharts.min.js into the package (currently CDN)
  for fully-offline/open-source distribution.
- Form 4 insider transactions still the top roadmap item.

---

# Session 2026-07-06 (part 3): analytics, screener, options, macro, events

## What was asked

Scale toward "full Bloomberg": advanced analytics, more asset classes
(fixed income, FX, derivatives, macro), screening, portfolio/risk mgmt,
corporate events (earnings, analyst data, meetings, Fed), technical
studies (ORB/EMA), TradingView integration, quant scripting, Schwab
Trader API. Clarified scope via AskUserQuestion: build all free chunks;
FRED as optional key (user initially confused, explained, proceeded);
Schwab = not now; quant scripting = the library itself, not server-side
code execution (RCE risk).

## Key discovery: Yahoo's auth wall + the crumb workaround

Probed live before building: v7/finance/quote, v10/quoteSummary, and
v7/finance/options ALL return 401 anonymously now. The classic
workaround (GET fc.yahoo.com for a cookie, then /v1/test/getcrumb, then
pass crumb= on every call) works and is what yfinance does. Built
`yahoo_auth.py` around it with the hard rule that its consumers (events,
options) degrade to "unavailable" instead of raising - only the chart
endpoint (quotes/history/screener) stays crumb-free.

## What was built (11 new/changed modules, tests 48 -> 106, MCP 11 -> 17 tools)

- `indicators.py` - SMA/EMA/RSI/MACD/Bollinger/ORB, pure math.
- `yahoo_auth.py` - cookie+crumb session, cached, refresh-once-on-401.
- `events.py` - earnings date + analyst mix (Yahoo), DEF 14A meetings
  (EDGAR), Fed press/speeches (official RSS).
- `options.py` - OMON-style chains (crumb-authed).
- `macro.py` - Treasury yield curve (keyless), BLS unregistered tier,
  FRED behind optional FRED_API_KEY.
- `screener.py` - SEC-XBRL-based screener, curated ~45-name universe,
  per-day disk cache, ONE companyfacts fetch per symbol (multi-MB).
- `risk.py` - vol/drawdown/Sharpe for a personal portfolio.
- `market.py` - Quote grew history_high/low/volume (for ORB).
- `fundamentals.py` - shares outstanding from dei taxonomy (market cap).
- Dashboard: TradingView advanced-chart embed in DES (their full study
  library), STUDIES + EVENTS panels, and 4 new screens: EQS, OPT, ECO,
  PF (localStorage personal portfolio). F1-F9 chips.
- MCP: +get_corporate_events, get_fed_calendar, get_macro_snapshot,
  screen_securities, get_options_chain, analyze_portfolio_risk.

## Live-found bugs this session

1. **Treasury OData namespaces**: values nest under `<m:properties>`
   (metadata ns); parser AND its hand-built fixture both wrongly used
   the d: ns -> tests green, live empty. Rewrote with local-name
   matching; fixture now copies the real feed. Full curve verified live.
2. **TradingView embed URL fails silently**: wrong (plausible) script
   host = no iframe, no console error. Correct:
   `s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js`.
3. Screener originally fetched companyfacts twice per symbol (metrics +
   shares) - halved to one fetch before first release.

## Verified live (browser + curl + MCP call_tool)

- DES NVDA: TradingView iframe, SMA20 202.33 / SMA50 209.66 / RSI 41.95
  / MACD -4.13, next earnings 2026-08-26, analyst "buy" (10/48/2/1/0).
- ORB AAPL during market hours: ABOVE_RANGE +0.87%.
- OPT AAPL: 23 expirations, 42 calls / 34 puts, sane IV/OI.
- ECO: 9-point curve for 2026-07-06 (10y 4.48%), real BLS CPI 335.123 /
  unemployment 4.2 / payrolls, 20 Fed items (Waller speech first).
- EQS (AAPL,MSFT,KO, P/E<=40): correctly passed MSFT 28.4 & KO 27.3 and
  filtered AAPL (41.9).
- /api/risk: 2-position portfolio, Sharpe 0.93.

## Still open / next

- FRED path is built but untested with a real key (user hasn't made one).
- Screener universe: consider a maintained-in-repo S&P 500 list or
  letting the dashboard pass the consensus/13F tickers as universe.
- Form 4 insider transactions remains the top "who purchased what" add.
- Schwab/brokerage: explicitly deferred by user ("not now").

---

# Session 2026-07-06 (part 2): full terminal screens + MCP server

## What was asked

"Add all the stuff available in a Bloomberg terminal... this is gonna be
open source where anyone can plug it to their AI."

Scoped honestly: Bloomberg's licensed feeds (real-time L2, chat,
execution) can't be replicated free; built the classic *screens* that can
be, plus an MCP server for the "plug into AI" part.

## What was built

- `views.py` - shared view layer. Flask endpoints and MCP tools are both
  thin wrappers over the same functions, so browser and AI see identical
  data. `Services` bundles all clients; `DashboardServices` aliases it.
- `fundamentals.py` (FA) - SEC XBRL companyfacts, ticker->CIK via SEC's
  company_tickers.json. Annual 10-K metrics only; a >=300-day duration
  check drops the quarterly comparatives 10-Ks also tag.
- `views.holders_view` (HDS) - which tracked managers hold a ticker;
  resolves every preset CUSIP once (disk-cached), ~1 min first run.
- `dashboard.html` v2 - command bar (`AAPL DES`, `MSFT FA`, `KO HDS`,
  `buffett PORT`, `MKTS`, `WATCH`, `HELP`), five screens, clickable
  tickers everywhere, range-selectable SVG chart, watchlist in
  localStorage.
- `mcp_server.py` + `edgar13f mcp` - FastMCP stdio server, 11 tools,
  optional dep (`pip install "edgar13f[mcp]"`).
- New CLI: `facts`, `holders`, `mcp`. Tests 37 -> 48, all offline.

## Live-found bug #3: day-change semantics

Yahoo's `chartPreviousClose` is the close before the *range start*, so
`change_pct` was actually range drift (AAPL "+10.18%" was a 5-day move;
part 1's portfolio %CHG column was showing 1-month moves). Fix: with
daily bars, previous close = second-to-last bar; the DES stats fetch a
separate daily quote and show CHG (1D) and CHG (RANGE) as distinct rows.

## Verified live

- DES AAPL: px 312.66, +1.31% (1d) vs +20.10% (6mo), 52w 201.5-317.4,
  123 chart bars, FA showing Apple's real FY2021-2025 (FY2024 rev
  $391.0B / EPS 6.08 - matches the actual 10-K), HDS showing Berkshire's
  227.9M shares / $57.84B / 22% weight.
- MCP: `call_tool("get_quote", ...)` returned real AAPL + ^GSPC data.
- MKTS/WATCH screens render from live Yahoo data.

---

# Session 2026-07-06 (part 1): Bloomberg-style dashboard + market data + news

## What was asked

"Add a Bloomberg-style dashboard, with functionality exceeding Bloomberg,
and add sources like Yahoo Finance and other finance sources for market
info and accurate news."

## What was built (all free/keyless, per the standing constraint)

- `market.py` - Yahoo Finance v8 chart endpoint client (`Quote` with
  price, prev close, 1-mo sparkline). All failures -> `None`, never raise.
- `tickers.py` - `CusipTickerResolver`: OpenFIGI keyless mapping of 13F
  CUSIPs to Yahoo tickers, batches of 5 @ 3s, disk-cached forever in
  `~/.edgar13f/cusip_tickers.json` (network failures NOT cached).
- `news.py` - RSS aggregation: Yahoo Finance (market + per-ticker), CNBC,
  MarketWatch, SEC press releases. Broken feeds skipped, deduped, sorted.
- `consensus.py` - the old wishlist #1: cross-manager CUSIP overlap with
  per-manager portfolio weights (`edgar13f consensus`).
- `cache.py` - old wishlist #2: holdings cached by accession number under
  `~/.edgar13f/holdings/`; wired into CLI, dashboard, consensus.
- `dashboard.py` + `dashboard.html` - Flask JSON API + single-file dark
  terminal UI (`edgar13f dashboard`, port 8813). World tape, portfolio w/
  live px + sparklines + weights, Q/Q changes, allocation bars, consensus
  panel, news panel scoped to held tickers. `.claude/launch.json` exists
  for the Claude Code preview panel.
- New CLI commands: `quote`, `news`, `consensus`, `dashboard`. New dep:
  flask. Tests went 11 -> 37, all offline/mocked.

## Live-found bugs (why live verification keeps paying off)

1. **13F `<value>` units were wrong by 1000x.** The field was named
   `value_usd_thousands` and displayed as "$000s", but since SEC's Jan
   2023 amendment filers report *whole dollars* - Berkshire's reported
   total (263,095,703,570) only makes sense as $263B, not $263T. Renamed
   to `value_usd` everywhere and fixed all labels. Pre-2023 filings DID
   use thousands; documented in the `Holding` docstring.
2. **OpenFIGI's first listing for a CUSIP isn't always the US ticker.**
   Chevron's CUSIP returned stale "CHV" before the US-composite "CVX";
   Yahoo has no CHV quote. `_extract_tickers` now prefers
   `exchCode == "US"` (regression test added).

## Verified live (browser + curl against the running dashboard)

- Buffett portfolio: Q1 2026 filing, 29 positions, $263.10B total, AAPL
  $57.84B @ 22% wt, real quotes + sparklines for 24/25 top names.
- Chubb (Swiss issuer) has no keyless OpenFIGI US mapping -> renders
  tickerless with no price, by design. Candidate fix: name-based fallback
  via SEC's `company_tickers.json`.
- Consensus found GOOGL held by buffett + ackman. News panel pulled real
  per-ticker headlines. Tape pulled indices/futures/crypto/FX.
- First portfolio load of a manager is slow (~20s: OpenFIGI keyless
  throttle); subsequent loads are instant thanks to both caches.

---

# Session 2026-06-30 (previous)

This file is the narrative of *what happened and why* in the
working session, 2026-06-30.

## What was asked

1. Dockerize the CLI (previous ask, already done before this segment).
2. "Nothing going through my head, go ahead and finish" - i.e. use
   judgment to close out the open items and hand back a clean state.

## What I did, in order

### 1. Verified the live SEC API path for the first time ever

This scaffold was originally built offline with no network access, so
nothing had ever round-tripped against real sec.gov servers. Built a
`Dockerfile` + `.dockerignore`, then ran `edgar13f search berkshire` and
`edgar13f holdings buffett` live via `docker run`.

**Found a real bug immediately:** `search_company_cik` parsed
`output=atom` from `/cgi-bin/browse-edgar`, but SEC's atom feed has a
server-side bug where `<entry title="...">` renders as a stringified Perl
array ref (`"ARRAY(0x55d6f0feff88)"`) instead of the company name. The
offline mocked tests never caught this because the mock XML was hand-built
correctly. Fixed by switching to parsing the default HTML results table
(`tree.xpath('//table[@class="tableFile2"]/tr[...]')`), verified against
live data, and added a regression test
(`test_search_company_cik_parses_html_table`) using a real anonymized HTML
fixture so this doesn't silently regress.

`holdings buffett` worked correctly on the first live try - XML namespace
handling and submissions JSON parsing were both right as originally built.

### 2. Closed out the three "not done" items from CLAUDE.md

**Retry/backoff** (`client.py::_get`): now retries up to 3 times on
429/5xx with exponential backoff, honoring `Retry-After` if present.
Non-retryable 4xx (404, etc.) still raise immediately - no wasted retries
on client errors. The existing ~10 req/sec self-throttle was left alone
per the CLAUDE.md constraint against removing it for speed.

**Pagination** (`client.py::list_13f_filings`): before touching code,
fetched a real long-history filer's submissions live (Icahn, CIK 921669)
to confirm the actual shape of `filings["files"][]` rather than guessing
from docs. Confirmed: each `files[]` entry names a JSON page at
`data.sec.gov/submissions/{name}`, and that page is a **flat dict** with
the same array-of-arrays shape as `recent` - *not* nested under a
`"filings"` key like `recent` is. `list_13f_filings` now walks `recent`
first, then those pages in filing-date order, stopping once `limit` 13F-HR
filings are collected.

**Quarter-over-quarter diffing** - this was CLAUDE.md's #1 "actually
interesting feature," so built it:
- `src/edgar13f/diff.py::diff_holdings(prior, current)` - pure function,
  no HTTP. Aggregates `Holding`s by CUSIP *within* each filing first
  (necessary: Berkshire's own 13F lists AAPL across 5 separate infoTable
  entries in one filing, split some other way internally), then compares
  the two aggregated snapshots and classifies each CUSIP as NEW / SOLD /
  INCREASED / DECREASED / UNCHANGED.
- `HoldingChange` dataclass added to `models.py`.
- `edgar13f diff <cik-or-preset>` CLI command, with `--csv` and
  `--show-unchanged` (unchanged positions are hidden by default - noise).
- Verified live: `edgar13f diff buffett` correctly diffed Berkshire's
  Q4 2025 -> Q1 2026 filings. Notably it correctly surfaced Alphabet
  (GOOGL/GOOG) and Lennar (LEN/LEN.B) as *two separate rows each* - these
  are genuinely different CUSIPs for different share classes, so that's
  correct output, not a duplicate-row bug. Worth remembering if it looks
  surprising later.

### 3. Test suite

Went from 4 tests to 11, all offline/mocked, all passing:
- `tests/test_client.py` - added pagination, retry-then-succeed,
  retry-exhausted, and non-retryable-4xx cases, plus the earlier HTML
  search-parsing regression test.
- `tests/test_diff.py` (new) - classification of all 5 statuses, and the
  multi-infoTable-per-CUSIP aggregation case.

Run with:
```bash
docker run --rm -v "$(pwd):/app" --entrypoint sh edgar13f:latest \
  -c "pip install -q pytest responses && python -m pytest -v"
```
(or locally: `pip install -e ".[dev]" && pytest -v`)

## Current state

- Docker image builds clean: `docker build -t edgar13f:latest .`
- 11/11 tests pass offline.
- `search`, `holdings`, and `diff` all verified against the live SEC API
  this session, not just offline mocks.
- `EDGAR_USER_AGENT` used for live testing: `"Vineeth Mudda
  vineethmudda@gmail.com"` (matches the user's email on file).

## What's still open

From CLAUDE.md, one item remains:
- **Pre-2013ish filers using `.txt` SGML instead of XML** for the
  information table - still untested. `get_information_table` should
  raise a clear error on these (by design) rather than silently failing,
  but that path has never been exercised against a real old filing. If
  picking this up: find an old 13F-HR (pre-~2013) via `edgar13f search`,
  fetch its filing index live, and confirm the error message is actually
  useful rather than a raw parse traceback.

Next features, in the order CLAUDE.md now recommends (updated this
session since diffing is done):
1. Multi-manager comparison ("which stock do the most famous investors
   agree on right now") - could reuse `diff_holdings`'s CUSIP-aggregation
   pattern across N managers instead of 2 filings.
2. Simple caching layer (sqlite or JSON keyed by accession number) -
   filings are immutable once filed, so repeated `diff`/`holdings` calls
   are needlessly re-fetching the same XML.
3. Expand `presets.py` beyond the current 5 - verify each new CIK via
   `edgar13f search` first, don't guess.
4. If heading toward public release: GitHub Actions (lint + pytest on
   push), a CHANGELOG, PyPI publishing.

## Gotchas worth remembering

- **SEC's `output=atom` company search is broken server-side.** Don't
  revert to it. The HTML table is the reliable source for company-name
  search results.
- **A single 13F can list one CUSIP multiple times.** Always aggregate by
  CUSIP within a filing before doing anything quarter-over-quarter or
  ranking-related. `diff.py::_aggregate_by_cusip` is the reference
  implementation if this comes up elsewhere.
- **`files[]` pagination pages are flat, `recent` is nested.** Both live
  under `data["filings"]`, but `recent` is `data["filings"]["recent"]`
  while a fetched page *is* the block directly (no `["filings"]["recent"]`
  wrapper on the paginated page itself).
- Docker Desktop on this machine has occasionally evicted a freshly built
  local image between commands (`docker images` came up empty after a
  successful build+run). If `docker run` says "pull access denied" for a
  clearly-local tag, just rebuild - it's fast because layers cache.
